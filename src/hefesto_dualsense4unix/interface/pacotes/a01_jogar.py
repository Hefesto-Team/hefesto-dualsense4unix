#!/usr/bin/env python3
"""O pacote da aba `01` Jogar — a que MAIS escreve, e a única com gesto ligado.

O QUE TEM DONO, medido no `state_full` de 01/09/2026:

    active_profile      o perfil em vigor                    ← tem dono
    controllers[]       a mesa: quantos, por qual transporte ← tem dono
    battery_pct         a carga de cada um                   ← tem dono
    player              o número de cada um                  ← tem dono
    vpad_backend        a máscara que o jogo vê              ← tem dono
    emulation_suppressed  o Hefesto está fora do meio?       ← tem dono

O MODO (o chip aceso da fileira) NÃO SAI DO STATE DIRETO: quem o lê é
`mode_transition.mode_of_state`, o ponto único de leitura do modo vivo, e ele
devolve TRÊS valores — nunca um quarto. O piloto já usa isso para acender o
interruptor, e é por isso que o botão da Jogar funciona hoje.
"""
from __future__ import annotations

from typing import Any

from . import Contexto, jogador_de, registrar


@registrar("01-jogar.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """Os valores da aba Jogar, com os NOMES que a página tem.

    CADA CHAVE AQUI É UM `data-campo` DO `01-jogar.html`, e isso não é
    coincidência: até 01/09/2026 os dois lados foram escolhidos separadamente, e
    esta aba pintava UM valor de cinco. O pacote emitia `mascara` e a página
    tinha `identidade`; emitia `conta_b` e a página tinha `conta-b`. Nenhuma
    máquina sabia que eram a mesma coisa, e o `querySelector` de um endereço que
    não existe não levanta — devolve `null`, e a pintura escreve zero.

    `src/hefesto_dualsense4unix/interface/casamento.py` é a régua que passou a medir isso.
    """
    cartoes = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # A IDENTIDADE É `nome · via`, como o desenho a escreve ("Cosmic Red
        # · USB") — e não a máscara. Sai da MESA, que é quem já leu a cor do
        # plástico; o `conectados` cru não tem o nome do modelo.
        casa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})
        nome = casa.get("nome") or "—"
        via = casa.get("via") or (c.get("transport") or "").upper()
        cartoes[uniq] = {
            # A COR DO PLÁSTICO — 03/09/2026, IDENTIDADE-VEM-DE-CIMA-01. Ela é a
            # borda do cartão, e até hoje vinha cravada do desenho: com o
            # controle DELA no cabo (White) a borda continuava Cosmic Red, três
            # centímetros abaixo de uma fita que já dizia White. A lei é dela:
            # *"se no topo tá mostrando controle white player 1, então cada aba
            # vai usar os controles lá de cima. Não mistura com a info dos
            # mockups."*
            #
            # `""` QUANDO NÃO SE SABE, e não é desistência: a cor chega pelo
            # broker, uma vez por endereço e em thread, então o primeiro tique
            # de uma sessão tem a mesa sem cor — e o controle por RÁDIO pode não
            # ter cor nenhuma enquanto a ONDA-CONEXOES-11 não entrar. O alvo
            # `cor` apaga o `style.color` no vazio e a pele volta ao neutro do
            # CSS. Regra dela: campo sem informação não mostra nada.
            "plastico": _cor_do_plastico(str(casa.get("cor") or "")),
            # `jogador_de` E NÃO `c.get("player")`: o daemon publica DUAS
            # chaves, e o `player` volta `None` no controle que o co-op não
            # numerou — medido em 02/09/2026 com o do CABO. Ler só ele escrevia
            # "Player —" na tela para um controle que a Iluminação, três linhas
            # abaixo, mostrava com o botão 2 ACESO. O dono lê `player_slot`
            # antes, que é a ordem da GTK (`controller_card.py:1059-1067`).
            "jogador": f"Player {jogador_de(c) or '—'}",
            "bateria": f"{c.get('battery_pct')}%" if c.get("battery_pct") is not None else "—",
            "identidade": f"{nome} · {via}",
        }

    # O AVISO SAI DO MESMO EXAME DA ABA CONEXÕES, e não de uma segunda leitura:
    # `integrations/exame_da_mesa` é o dono, e duas contagens do mesmo fato
    # divergiriam no primeiro achado novo.
    achados = _do_exame()
    grave = next((a for a in achados if a["grave"]), None) or (achados[0] if achados else None)

    # A FAIXA LARANJA. Os dois endereços saem daqui SEMPRE — inclusive vazios —
    # porque o que estava cravado na página é uma frase, e uma frase só se apaga
    # escrevendo por cima. Ver `_faixa_do_pendente`.
    frase, alvo = _faixa_do_pendente(ctx.state)

    fora = {
        "atencao-conta": f"{len(achados)} aviso" + ("s" if len(achados) != 1 else ""),
        "cartoes": cartoes,
        "pendente": frase,
        "pendente-alvo": alvo,
        # QUATRO POR CARTÃO desde 03/09/2026 — eram três, e o quarto é o
        # `plastico`. Este número é a promessa que a aba faz; deixá-lo em três
        # depois de acrescentar um campo é o começo de um contador que mente, e
        # ele é O instrumento com que esta casa prova que um endereço existe.
        "cobertura": {"pintados": 3 + len(cartoes) * 4 + (2 if grave else 0), "sem_dono": 0},
    }
    if grave:
        fora["aviso-selo"] = grave["selo"]
        fora["aviso-texto"] = grave["titulo"]
    # `perfil`, `conta` e `conta-b` NÃO saem daqui: são do cabeçalho, que é das
    # dez abas, e o dono deles é `pacotes.topo()`. Emiti-los aqui criava um
    # segundo dono — e foi assim que `conta_b` (com underscore) conviveu com o
    # `conta-b` da página sem nunca casar.
    return fora


def _cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, ou `""` quando ninguém sabe ainda.

    O DONO DO HEX É `monta.cor_da_zona`, e ele não se digita: ele LÊ a folha que
    pinta o desenho (`scripts/gerar_cores_do_dualsense.py`), que por sua vez sai
    do `docs/data/cores-do-dualsense.csv` — 28 modelos e 10 zonas. É a mesma
    fonte que o chip da fita usa, e é o que faz a borda do cartão não poder
    discordar do chip três linhas acima.

    POR QUE ESTA GUARDA EXISTE EM VEZ DE CHAMAR `cor_da_zona` DIRETO:
    `cor_da_zona` levanta `SystemExit` para colorway que o SVG não tem, e um
    modelo novo derrubaria a pintura da aba INTEIRA — trocaríamos uma borda que
    falta por uma tela congelada. O `""` é o caminho honesto: sem hex, sem cor.

    ELA É GÊMEA DA `a04_iluminacao._cor_do_plastico`, e a cópia é deliberada.
    Importar a privada de outra aba acopla esta aba ao arquivo que outra frente
    está editando no mesmo dia; o que NÃO se duplica é o dado — o hex continua
    tendo um dono só, e é o `cor_da_zona` que as duas chamam.

    O `except` PEGA `BaseException` DE PROPÓSITO, e não é descuido: `SystemExit`
    **não** herda de `Exception`, então um `except Exception` aqui deixaria
    passar exatamente o caso que esta guarda existe para segurar. A gêmea da
    `a04` escreve `except Exception` e por isso não segura nada — está anotado
    para quem cuidar daquela aba.
    """
    if not slug:
        return ""
    try:
        import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

        return str(monta.cor_da_zona(slug))
    except BaseException:
        return ""


def _do_exame() -> list[dict[str, Any]]:
    """Os achados do exame da mesa, ou lista vazia. Nunca levanta."""
    try:
        from . import a08_conexoes

        return [{"selo": "RÁDIO" if i["grave"] else "AVISO", **i}
                for i in a08_conexoes._exame()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# A FAIXA LARANJA — o que ela escolheu e o daemon ainda NÃO alcançou
# ---------------------------------------------------------------------------
#: O QUE A FAIXA DIZIA, E POR QUE ISSO ERA FALSO — medido em 02/09/2026, na foto
#: da aba com os dois controles dela na mesa:
#:
#:     ● Vai mudar para **Sony DualSense** quando você clicar em **Aplicar**
#:
#: e, na MESMA foto, o chip **Sony DualSense** já estava aceso na fileira Modo.
#: As duas metades da frase estão erradas, e cada uma por um motivo diferente:
#:
#: 1. **"Vai mudar para Sony DualSense"** é tautologia. O gerador deriva a
#:    palavra de `aba01.MODO_ACESO` desde 31/08 — a cura que ela encomendou ao
#:    ver a faixa anunciar "Modo Nativo" com o interruptor em Ligado. A cura
#:    matou a CONTRADIÇÃO e deixou no lugar uma frase que só sabe prometer o que
#:    já está valendo: cravada em `MODO_ACESO`, ela nunca poderá dizer outra
#:    coisa.
#: 2. **"quando você clicar em Aplicar"** é falso em TODO estado desta interface.
#:    O Aplicar daqui é `pacotes/rodape.aplicar`, que manda
#:    `profile.apply_draft` com o `to_ipc_dict()` do rascunho — e o contrato
#:    desse payload, escrito no próprio produto (`app/draft_config.to_ipc_dict`,
#:    PERFIL-SALVA-TUDO-01), é: *"`mode` e `suppress_desktop_emulation` … NÃO
#:    viajam no 'Aplicar'"*. **Clicar em Aplicar não troca modo nem máscara.**
#:    Na janela GTK a frase era verdadeira porque `footer_actions.on_apply_draft`
#:    tem um SEGUNDO ramo (`_aplicar_escolha_pendente` → `apply_mode`); o rodapé
#:    desta interface não tem, e a docstring dele já dizia isso com todas as
#:    letras — *"a interface nova ainda não guarda"*.
#:
#: O QUE A FAIXA PASSA A DIZER, e é o que ela SEMPRE existiu para dizer
#: (AGORA-E-DEPOIS-01, `relancar.texto_do_pendente`): *"esta é a única prova de
#: que o clique registrou"*. Nesta interface o clique aplica na hora (decisão
#: dela, 01/09), então uma pendência só nasce quando o daemon **não alcançou** o
#: que ela pediu — e é justamente aí que a tela estava MUDA. `_aplicar` não
#: levanta com o retorno de propósito (ver `ACHADO_DO_TIMEOUT`), então um clique
#: que não pega hoje não deixa rastro nenhum na tela.
_ESCOLHA: dict[str, str] = {}
#: A PALAVRA QUE ELA LEU NA TELA, por campo pendente. Ela NÃO é digitada aqui e
#: não sai de tabela nenhuma: chega no clique, em `o["texto"]` — o
#: `textContent` do próprio botão que ela apertou (`hefesto_vivo.BOOTSTRAP`,
#: `manda_do_alvo`). É a única fonte que não pode divergir do desenho, porque É
#: o desenho. O `painel.CHIPS_DA_ESCADA` é a rede de segurança, e a chave crua é
#: o último degrau — nunca um nome inventado.
_ROTULO: dict[str, str] = {}


def _lembrar(campo: str, valor: str, rotulo: str) -> None:
    """Anota o que ela acabou de pedir. Escritor ÚNICO dos dois dicionários.

    `campo` é `"modo"` ou `"mascara"`, que são as duas chaves de
    `home_actions.reconciliar_pendente` — as mesmas da janela estável. Escrever
    um terceiro nome aqui faria a reconciliação passar batido por ele.
    """
    if not valor:
        return
    _ESCOLHA[campo] = valor
    _ROTULO[campo] = rotulo or _rotulo_de(campo, valor)


def _rotulo_de(campo: str, valor: str) -> str:
    """A palavra aprovada por ela para aquela chave, sem passar pela tela.

    Rede de segurança para quando o clique não trouxe `texto` (um dublê de
    régua, um botão que a pintura trocou no meio). Sai de
    `painel.CHIPS_DA_ESCADA`, que é o dono dos rótulos da fileira — digitá-los
    aqui seria a segunda cópia da palavra dela.
    """
    if campo == "mascara":
        for chip in _painel().CHIPS_DA_ESCADA:
            ponte = chip.ponte
            if ponte is not None and ponte.mascara == valor:
                return str(chip.rotulo)
    return valor


def _pendencia(state: dict[str, Any]) -> dict[str, str]:
    """O que ela pediu MENOS o que o daemon já alcançou. Devolve o que sobra.

    A REGRA NÃO SE REESCREVE: `home_actions.reconciliar_pendente` é a dona dela
    desde a AGORA-E-DEPOIS-01, e a frase que a define está lá — *"uma pendência
    só existe enquanto DIVERGE do vigente"*. Ela lê tudo por `getattr`, então
    serve a qualquer objeto: aqui vai um `SimpleNamespace`, porque esta
    interface não tem uma `janela` onde pendurar a escolha.

    AS DUAS PONTAS TAMBÉM TÊM DONO: o modo vivo é `mode_transition.mode_of_state`
    (o mesmo que acende o interruptor) e a máscara viva é
    `home_actions.mascara_do_aparelho` — que sabe a diferença entre a máscara
    EXPLÍCITA e a deduzida do `backend`, e devolve `None` quando não dá para
    saber. Comparar contra um `None` não apaga pendência nenhuma, que é o
    comportamento certo: não saber não é ter alcançado.

    DAEMON CALADO NÃO RECONCILIA. É o ramo `visivel=False` do
    `home_actions.render_pendente`: *"sem daemon não há como aplicar, mas o que
    ela decidiu não pode evaporar por causa de um engasgo de IPC"*. Sem isto o
    `mode_of_state({})` devolveria `desktop` — ele só devolve `None` para um
    não-dicionário — e um pedido de Navegação seria dado por cumprido por um
    tique sem resposta.
    """
    if not state:
        return dict(_ESCOLHA)
    from types import SimpleNamespace

    from hefesto_dualsense4unix.app.actions.home_actions import (
        mascara_do_aparelho,
        reconciliar_pendente,
    )
    from hefesto_dualsense4unix.app.actions.mode_transition import mode_of_state

    lembrete = SimpleNamespace(
        _escolha_pendente=dict(_ESCOLHA) or None,
        _modo_vigente_do_daemon=mode_of_state(state),
        _mascara_vigente_do_daemon=mascara_do_aparelho(state),
    )
    sobra: dict[str, str] = dict(reconciliar_pendente(lembrete) or {})
    _ESCOLHA.clear()
    _ESCOLHA.update(sobra)
    for campo in [c for c in _ROTULO if c not in sobra]:
        del _ROTULO[campo]
    return sobra


def _faixa_do_pendente(state: dict[str, Any]) -> tuple[str, str]:
    """`(frase, alvo)` da faixa laranja — `("", "")` quando não há pendência.

    A FRASE É DO PRODUTO: `relancar.texto_do_pendente` é função pura (zero GTK,
    zero import além do `typing`) e é a MESMA que a janela estável escreve na
    linha do pendente. O marcador `●` vem de lá também
    (`relancar.MARCADOR_PENDENTE`).

    A MAIÚSCULA É REGRA DESTA LINHA, e é dela — 28/08/2026, e o comentário do
    gerador a guarda: *"o `●` que vem antes é MARCADOR, não palavra: a frase
    começa aqui"*. A janela estável escreve a mesma frase em minúscula porque lá
    ela é um rótulo no meio de outros; aqui é a linha inteira, isolada na caixa
    tracejada. É a única coisa que este arquivo faz com o texto do produto, e
    fazê-la aqui é o que evita uma segunda cópia da frase.

    O VAZIO É `""` DE PROPÓSITO: o piloto escreve `—` no lugar de um valor vazio
    (`hefesto_vivo.BOOTSTRAP`, `escrever`), que é a palavra desta casa para *"não
    há"* — a mesma de `painel.SEM_LEITOR`. Uma faixa com travessão diz "nada
    pendente"; a frase cravada do desenho dizia uma mudança que não vem.
    """
    from hefesto_dualsense4unix.app.actions.relancar import (
        MARCADOR_PENDENTE,
        texto_do_pendente,
    )

    sobra = _pendencia(state)
    if not sobra:
        return "", ""
    rotulos = [_ROTULO.get(c, sobra[c]) for c in ("modo", "mascara") if c in sobra]
    frase = texto_do_pendente(
        modo=_ROTULO.get("modo", sobra.get("modo")) if "modo" in sobra else None,
        mascara=(_ROTULO.get("mascara", sobra.get("mascara"))
                 if "mascara" in sobra else None),
    )
    marca = f"{MARCADOR_PENDENTE} "
    if frase.startswith(marca):
        resto = frase[len(marca):]
        frase = marca + resto[:1].upper() + resto[1:]
    return frase, ", ".join(rotulos)


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao daemon
# ---------------------------------------------------------------------------
# NADA SE REESCREVE, e nesta aba isso é mais que uma regra de estilo: a
# sequência de IPC de cada modo é uma DEFINIÇÃO do produto, não um detalhe de
# tela. Quem a possui é `app/actions/mode_transition.plan_mode_transition`,
# desde o HARM-01 — o sprint que nasceu porque o modo tinha DOIS donos e eles
# discordavam (a Início saía do Modo Nativo antes de ligar o gamepad; a Emulação
# chamava `gamepad.emulation.set` cru, e os dois ficavam ligados juntos: o
# físico grabado pelo jogo e o vpad congelado — jogo sem controle nenhum).
#
# Escrever aqui `p.chamar("gamepad.emulation.set", enabled=True)` seria o
# terceiro dono. Então esta aba **pergunta**:
#
#     painel.plano_do_modo(chave, mascara) -> [(metodo, params), ...]  # (noqa-acento) id
#
# que delega ao `plan_mode_transition` sem uma linha de regra própria, e devolve
# `None` quando o botão não tem escritor. A tradução chip → máscara também não é
# digitada: sai de `painel.CHIPS_DA_ESCADA`, que é onde a casa guarda qual ponte
# cada chip da fileira nomeia.
from . import gesto  # noqa: E402

#: OS BOTÕES DESTA ABA QUE **NINGUÉM ATENDE**, com o motivo medido. Eles saem do
#: gerador COM `data-gesto` e sem `@gesto`: o piloto recusa dizendo o nome, e o
#: nome aparece no relato como inventário do que falta. É a única forma honesta
#: — sem o endereço o clique some calado, e quem clicou conclui que funcionou.
BOTOES_SEM_DONO: dict[str, str] = {
    "modo-steam": (
        "não há IPC de Steam Input entre os métodos que o daemon atende, e o "
        "degrau custa o que nenhum socket paga: `UseSteamControllerConfig` só "
        "sobrevive com a Steam FECHADA (a Steam regrava o `localconfig.vdf` ao "
        "sair — `integrations/steam_input_ponte.py`), então ligar exige fechar "
        "a Steam, reabrir a Steam e reabrir o jogo "
        "(`integrations/ponte_escada.py`, § OS DOIS TRAMOS)."
    ),
    "mascara": (
        "a máscara do gamepad virtual é UMA para a máquina, não uma por "
        "controle: `gamepad.emulation.set` recebe `flavor` e não recebe `uniq` "
        "(`daemon/ipc_handlers.py:5060`). E 'Nintendo Pro' não é máscara do "
        "produto — o portão de entrada recusa em voz alta tudo o que não for "
        "`dualsense`/`xbox` e sinônimos (`ipc_handlers.py:5090`)."
    ),
}


def _painel() -> Any:
    """`app/actions/jogar/painel` — o dono das perguntas desta aba.

    Importado DENTRO das funções, e não no topo: `painel` puxa `home_actions`,
    que puxa GTK.

    FATO ERRADO, SUBSTITUÍDO — 02/09/2026. Esta linha dizia que sem o import
    tardio *"as dez abas carregariam GTK para pintar um travessão"*. **GTK já
    chega antes de qualquer aba**, e a medição é de uma linha:

        import pacotes            ->  38 módulos `gi` carregados
        import pacotes.a01_jogar  ->  os mesmos 38, nenhum a mais

    Quem o traz é o próprio despachante, por `app/actions/base.py:9`. O import
    tardio segue valendo, e o motivo verdadeiro é OUTRO e menor: `painel` puxa a
    escada, as pontes e o prontuário dos jogos (217 ms de import frio contra
    166 ms do `mode_transition`, que não puxa GTK nenhum). É custo de partida,
    não de pureza — as funções de pacote continuam sem TOCAR GTK, que é o que o
    contrato do `pacotes/__init__` pede.
    """
    from hefesto_dualsense4unix.app.actions.jogar import painel

    return painel


def _plano(chave: str, mascara: str | None = None) -> list[tuple[str, dict[str, Any]]]:
    """A sequência de IPC daquele modo — DELEGADA, sem uma linha de regra aqui.

    `painel.plano_do_modo` devolve `None` quando o botão não tem escritor, e o
    motivo em português é de `painel.porque_nao_aplica`. Levantar com ELE é o
    que faz o botão recusar DIZENDO, em vez de falhar calado.
    """
    painel = _painel()
    plano: list[tuple[str, dict[str, Any]]] | None = painel.plano_do_modo(
        chave, mascara)
    if plano is None:
        raise RuntimeError(painel.porque_nao_aplica(chave))
    return plano


def _aplicar(p: Any, plano: list[tuple[str, dict[str, Any]]]) -> None:
    """Despacha o plano na ORDEM, pelo degrau 3 da ponte.

    NENHUM DESTES QUATRO MÉTODOS TEM FUNÇÃO NO `app/ipc_bridge.py` — conferido
    nas 36 que ele expõe: `native.mode.set`, `gamepad.emulation.set`,
    `mouse.emulation.restore` e `coop.sync` não estão lá. Então é `p.chamar`,
    que passa pelo mesmo `_safe_call` do bridge e herda o tratamento de erro.

    A ORDEM É A ENTREGA, e ela não é enfeite: `plan_mode_transition` põe o
    `native.mode.set {enabled: false}` ANTES do `gamepad.emulation.set` porque,
    invertidos, *"o vpad nasceria com o físico ainda grabado pelo jogo"*.

    O RETORNO NÃO VIRA ERRO, e o motivo está medido — ver `ACHADO_DO_TIMEOUT`.
    """
    for metodo, params in plano:
        p.chamar(metodo, **params)


#: ACHADO, 01/09/2026 — e ele fica escrito porque muda o que este arquivo pode
#: prometer: **`pacotes/ponte.chamar` não tem folga de tempo.** Ele chama
#: `_safe_call(metodo, params)` com o default de **250 ms**, que é o timeout de  # (noqa-acento) id
#: LEITURA da ponte, e desde o BUG-IPC-READ-NO-TIMEOUT-01 esse prazo cobre
#: também a resposta (`ipc_bridge._run_call`).
#:
#: Só que trocar de modo não é leitura: cria uinput e faz grab, e o produto
#: declara **2,0 s** para isso (`mode_transition.MODE_IPC_TIMEOUT_S`, cujo
#: comentário diz com todas as letras: *"sem folga o toast dizia 'Falha' com o
#: modo JÁ aplicado"*). O `profile.switch` teve a mesma cicatriz e ganhou 3,0 s
#: (`ipc_bridge.PROFILE_SWITCH_TIMEOUT_S`).
#:
#: CONSEQUÊNCIA PARA ESTES GESTOS: um `p.chamar("gamepad.emulation.set", …)`
#: pode voltar `False` com o modo aplicado. Por isso `_aplicar` **não** levanta
#: com o retorno — levantar aqui reintroduziria exatamente o defeito que o
#: `MODE_IPC_TIMEOUT_S` curou, e a tela diria "não deu" sobre um gesto que deu.
#: A cura de verdade é `chamar` aceitar `timeout=`, e ela mora em `ponte.py`,
#: que não é território desta aba.
ACHADO_DO_TIMEOUT = (
    "ponte.chamar() chama _safe_call com o timeout de LEITURA (250 ms); "
    "mode_transition.MODE_IPC_TIMEOUT_S declara 2,0 s para trocar de modo."
)


@gesto("01-jogar.html", "hefesto")
def hefesto(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O INTERRUPTOR: Ligado (`gamepad`) ou Desligado (`native`).

    QUAL POSIÇÃO É O `data-modo` do rótulo clicado, e ele chega em `o["modo"]`
    já — o mesmo endereço que a pintura viva usa para acender a posição a partir
    de `mode_of_state`. Um segundo atributo só para o clique faria a tela ter um
    endereço para ler e outro para escrever.

    **"Desligado" É O MODO NATIVO, e não "parar o Hefesto"** — decisão dela,
    31/08/2026: *"o modo nativo já existe ali (…) e se eu quiser desligar modo
    hefesto clico em desligado e o modo nativo fica online."* Parar o serviço
    continua sendo a aba Sistema, e é por isso que este gesto nunca chama
    `daemon.pause` nem toca em `systemctl`.

    POR QUE `plano_do_modo` E NÃO `apply_mode`: os dois delegam ao mesmo
    `plan_mode_transition`, mas `apply_mode` despacha por `call_async`, que
    devolve o resultado por `GLib.idle_add` — laço GTK, que o gesto não tem (ele
    roda numa thread do piloto). `plano_do_modo` devolve a MESMA sequência como
    dado, e quem a despacha é a ponte. Zero regra reescrita.

    O QUE ELE GRAVA NO DISCO, e é a resposta à pergunta dela *"não sei se segue
    desativado"*: o passo `gamepad.emulation.set` com `origin='manual'` é o que
    escreve (ou apaga) o `gamepad_disabled.flag` — `utils/session.
    save_gamepad_emulation`, citado em `painel.ESCRITOR_DOS_MODOS`. O
    `origin='manual'` não é decoração: sem ele o daemon lê o pedido como
    reconciliação automática e o recusa quando há Steam Input na jogada
    (ORIGEM-QUE-MENTE-01). Ele vem no plano, não é digitado aqui.
    """
    chave = str(o.get("modo") or "")
    if not chave:
        raise ValueError(
            "hefesto: o clique não disse qual posição do interruptor — o "
            "`data-modo` do rótulo não chegou")
    _aplicar(p, _plano(chave))
    # DEPOIS de despachar, nunca antes: `_plano` levanta para um botão sem
    # escritor, e anotar uma pendência que não chegou a sair prometeria uma
    # mudança que ninguém pediu ao daemon.
    _lembrar("modo", chave, str(o.get("texto") or ""))


def _plano_do_chip(chave: str) -> list[tuple[str, dict[str, Any]]]:
    """A sequência daquele chip da fileira — a máscara sai do PRODUTO.

    `painel.CHIPS_DA_ESCADA` é quem guarda qual ponte cada chip nomeia
    (`Ponte(KIND_GAMEPAD, MASCARA_DUALSENSE)` para o "Sony DualSense", `…XBOX`
    para o "Xbox"). Digitar `"dualsense"` aqui seria a segunda cópia de um valor
    que já tem dono — e que muda de lugar quando a `ESCADA` mudar.

    DOIS CAMINHOS, e a diferença é a que `painel` documenta: um chip com `modo`
    (a **Navegação**) É um modo do produto e vai por ele; os outros são
    MÁSCARAS do mesmo modo `gamepad`, e vão pelo `flavor` do plano.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_GAMEPAD
    from hefesto_dualsense4unix.integrations import ponte_escada

    chip = next((c for c in _painel().CHIPS_DA_ESCADA if c.chave == chave), None)
    if chip is None:
        raise ValueError(f"modo: {chave!r} não é chip da fileira desta aba")
    if chip.modo:
        # A Navegação: `apply_mode('desktop')`, os três IPCs em ordem.
        return _plano(chip.modo)
    ponte = chip.ponte
    if ponte is None or ponte.kind != ponte_escada.KIND_GAMEPAD or ponte.steam_input:
        raise RuntimeError(BOTOES_SEM_DONO.get(f"modo-{chave}", "sem dono no produto"))
    return _plano(MODE_GAMEPAD, ponte.mascara)


def _lembrar_do_chip(chave: str, o: dict[str, Any]) -> None:
    """Anota o que o chip clicado pediu, no EIXO dele — e só nele.

    UM CHIP MEXE NUM EIXO SÓ, e é o que o `_plano_do_chip` já diz: a Navegação
    **é** um modo (`chip.modo`), os outros são MÁSCARAS do mesmo modo `gamepad`
    (`chip.ponte.mascara`). Anotar `modo=gamepad` junto com a máscara poria na
    faixa a palavra do CHIP ("Xbox") sob o rótulo do INTERRUPTOR ("Ligado") —
    duas coisas com nomes diferentes na tela dela, coladas numa linha só.

    Qual eixo é de cada chip sai de `painel.CHIPS_DA_ESCADA`, e não de um `if`
    por nome: é o mesmo lugar de onde `_plano_do_chip` tira a ponte.
    """
    chip = next((c for c in _painel().CHIPS_DA_ESCADA if c.chave == chave), None)
    if chip is None:
        return
    rotulo = str(o.get("texto") or "")
    if chip.modo:
        _lembrar("modo", chip.modo, rotulo)
        return
    ponte = chip.ponte
    if ponte is not None and ponte.mascara:
        _lembrar("mascara", str(ponte.mascara), rotulo)


@gesto("01-jogar.html", "modo-dualsense")
def modo_dualsense(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Sony DualSense": o jogo desenha os botões do PlayStation.

    É a máscara `054c:0df2`, e ela é o PRIMEIRO degrau que o produto tenta —
    `ponte_escada.ESCADA[0]`. A razão está contada no cabeçalho de lá: **dez**
    linhas do `mapa-controles.csv` só chegam ao jogo por `uhid` (giroscópio,
    acelerômetro, touchpad, bateria, o jack de áudio, o rumble por FF…), e a
    máscara Xbox não tem onde pôr nenhuma delas. *"Errar para DualSense custa um
    aperto de botão; errar para Xbox custa dez linhas do mapa, e custa em
    silêncio."*

    O modo continua sendo `gamepad`: o que muda entre este chip e o "Xbox" é o
    `flavor`, não o modo. É por isso que o plano tem os mesmos dois passos.
    """
    _aplicar(p, _plano_do_chip("dualsense"))
    _lembrar_do_chip("dualsense", o)


@gesto("01-jogar.html", "modo-xbox")
def modo_xbox(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Xbox": o formato que todo jogo entende — o SEGUNDO que o Hefesto tenta.

    ESTE CHIP NASCEU EM 31/08/2026 E É UMA DÍVIDA PAGA: `Ponte(gamepad, xbox)` é
    degrau da `ESCADA` desde 19/08 e **nenhum chip o nomeava** — era o que
    `painel.degraus_sem_chip()` denunciava. A escada automática passava por ele
    e a tela não tinha onde mostrá-lo.

    O preço dele está medido e não se esconde: `045e:028e` é `uinput`, o pacote
    do Xbox 360 é fixo desde 2005, e quem escolhe esta máscara *"escolhe rumble
    por evdev que funciona em tudo e paga com as cinco features"*
    (`docs/protocol/pilha-steam-input-xpad-sdl.md` §1.5).
    """
    _aplicar(p, _plano_do_chip("xbox"))
    _lembrar_do_chip("xbox", o)


@gesto("01-jogar.html", "modo-navegacao")
def modo_navegacao(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Navegação": o controle vira teclado e mouse do computador.

    O CASO DO MEIO, e `painel` o explica melhor do que eu resumiria: a Navegação
    **não é degrau da `ESCADA`** (`KIND_DESKTOP` existe como constante e
    `indice_do_degrau` devolve -1 — por isso o PS+R3 não para aqui) e **tem
    escritor**: `apply_mode('desktop')` funciona hoje. Confundir as duas
    perguntas pintaria "sem dono" sobre um botão que dá — é a diferença entre
    `chips_sem_degrau()` e `chips_sem_dono()`.

    SÃO TRÊS IPCs, e o terceiro é o que faz a diferença entre entrar no modo e
    entrar num modo sem função: `mouse.emulation.restore` LIGA o mouse conforme
    a preferência que o daemon persistiu (HARM-06). Sem ele, o modo desktop
    desligava os outros dois e deixava o controle sem fazer nada até alguém
    achar a aba Mouse — foi o `MODO-QUE-NAO-CONTROLA-01`, medido com ela ao
    vivo: *"cliquei em aplicar e nada"*. E ele vem POR ÚLTIMO: ligar o mouse
    antes de o gamepad sair faria a exclusão mútua do daemon derrubar o mouse
    recém-ligado. A ordem é do plano, não daqui.
    """
    _aplicar(p, _plano_do_chip("navegacao"))
    _lembrar_do_chip("navegacao", o)


@gesto("01-jogar.html", "reconectar")
def reconectar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Reconectar Controles": os jogadores voltam, e a numeração se ajeita.

    O NOME DA TELA É DELA E É NOVO; o gesto não é. A legenda desta aba registra
    a troca — *"'Reconciliar jogadores' virou 'Reconectar Controles'"* — e o
    botão antigo é `home_actions._on_home_reconciliar_clicked`, que faz
    exatamente estes dois passos, encadeados.

    **NÃO É O `Connect` DO BLUEZ, e isso é decisão dela.** O
    `integrations/gesto_de_reconexao.py` diz com todas as letras: *"Não
    reconectar é decisão dela, e é o contrato deste módulo. O botão PS é dela;
    `reconectar` não existe aqui de propósito. Um `Connect` nosso devolveria o
    controle sem o gesto físico — e a instância que voltaria seria nossa, não
    dela."* O que este botão traz de volta é o JOGADOR, não o rádio.

    PASSO 1 — `coop.sync`: um ciclo FORÇADO de reconciliação
    (`CoopManager.sync(force=True)`). É o único caminho capaz de trazer de volta
    o jogador cujo grab foi recusado ou cujo vpad morreu sem que `/dev/input`
    mudasse: o ciclo normal do poll loop só reenumera quando `/dev/input` muda,
    e um vpad morto pode esperar o próximo hotplug para sempre
    (`ipc_handlers.py:5190`).

    PASSO 2 — `identity.renumber`: compacta a numeração preservando a ordem
    relativa. **A ORDEM É A ENTREGA** e está escrita no botão antigo
    (`home_actions.py:3122`): *"renumerar antes de reconciliar compactaria uma
    mesa que ainda não está completa."*

    E A RECUSA DO SEGUNDO NÃO É ERRO: com o jogo aberto o daemon recusa
    renumerar (repintar o LED do controle em uso no meio da partida é o defeito
    que a NUMA-03 fechou), e os jogadores já voltaram no passo 1. Tratar isso
    como falha seria a interface mentindo — é a mesma regra do
    `reported_step_index`. Por isso os dois passos vão sem levantar.
    """
    p.chamar("coop.sync")
    p.chamar("identity.renumber")


#: OS DOIS DESTA ABA NA LISTA DOS DEZESSEIS, classificados um a um — 02/09/2026.
#:
#: A régua do `--prova-no-aparelho` os marcou como *"sem efeito e sem `SEM_ECO`"*
#: (`docs/process/2026-09-02-O-MAPA-DA-INTERFACE-…` §2.3). **Nenhum dos dois é
#: caso de `SEM_ECO`**, e por isso esta aba continua sem declarar um: `SEM_ECO`
#: quer dizer *"o daemon não publica este assunto"* (é o caso do `trigger.set`,
#: que o DualSense não devolve). Os dois daqui o daemon publica — os cinco
#: métodos de `METODOS` mexem em `native_mode`, `gamepad_emulation`, `coop` e
#: `controllers[].player`, e as quatro chaves estão no `state_full`. Declará-los
#: `SEM_ECO` calaria a régua para sempre sobre um caminho que ela consegue medir.
#:
#: O QUE ELES SÃO, medido contra o estado vivo dela em 02/09 às 04:20
#: (`native_mode false` · `gamepad_emulation.enabled true` · `flavor dualsense`
#: · `coop.players 1` · dois controles, numeração já compacta):
#:
#:     hefesto      A prova clica o rótulo `data-modo="gamepad"`, que é a posição
#:                  **Ligado** — e o daemon JÁ ESTAVA em `gamepad`. Os dois IPCs
#:                  do plano são idempotentes: `native.mode.set{enabled:false}`
#:                  sobre um nativo já desligado e `gamepad.emulation.set
#:                  {enabled:true}` sobre uma emulação já ligada não mudam campo
#:                  nenhum. O gesto NÃO mentiu: ele foi aceito e não havia o que
#:                  mudar.
#:     reconectar   `coop.sync` é um ciclo FORÇADO de reconciliação e
#:                  `identity.renumber` compacta a numeração. Com a mesa já
#:                  reconciliada e já compacta, os dois são no-ops — e quando há
#:                  o que fazer, os dois aparecem em `coop` e em
#:                  `controllers[].player`.
#:
#: LOGO A LISTA DOS DEZESSEIS PRECISA DE UMA QUARTA CAIXA, e é a que faltava no
#: enunciado: além de *"recusou e o instrumento não leu"*, *"o daemon não ecoa"*
#: e *"mentiu"*, existe **"aplicou e não havia o que mudar"**. A régua não sabe
#: separá-la porque ela lê só o `state_full` ANTES e DEPOIS; separar exigiria
#: comparar o estado de ANTES com o que o gesto PEDIU, e isso é do piloto.
#:
#: O QUE ESTA ABA PODE FAZER, E FAZ A PARTIR DE HOJE: **dizer na tela quando o
#: pedido NÃO chegou.** É a faixa laranja (`_faixa_do_pendente`) — até agora um
#: clique que não pegava não deixava rastro nenhum, porque `_aplicar` engole o
#: retorno de propósito (`ACHADO_DO_TIMEOUT`).
OS_DOIS_DA_LISTA_DOS_DEZESSEIS: dict[str, str] = {
    "hefesto": (
        "aplicou e não havia o que mudar: a prova clica a posição Ligado e o "
        "daemon já estava em `gamepad` (`native_mode false`, "
        "`gamepad_emulation.enabled true`). Os dois IPCs são idempotentes."
    ),
    "reconectar": (
        "aplicou e não havia o que mudar: `coop.sync` reconcilia uma mesa já "
        "reconciliada e `identity.renumber` compacta uma numeração já compacta. "
        "Os dois ecoam em `coop` e em `controllers[].player` quando há o que fazer."
    ),
}

#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. Uma só, e o `chamar` é o degrau 3: os
#: quatro métodos abaixo não têm invólucro no `app/ipc_bridge.py` — conferido nas
#: 36 funções que ele expõe.
PONTE = {"chamar"}
#: OS MÉTODOS CRUS. A régua confere um a um contra o `ipc_server.py`, e um nome
#: inventado reprova AQUI, não na mão de quem clica.
METODOS = {
    "native.mode.set",
    "gamepad.emulation.set",
    "mouse.emulation.restore",
    "coop.sync",
    "identity.renumber",
}


#: O QUE ESTA ABA DECLARA À RÉGUA. O piso é CINCO, e não seis: o `modo-steam`
#: está marcado no desenho e **não** tem `@gesto` (ver `BOTOES_SEM_DONO`).
PAGINA = "01-jogar.html"
PISO_DA_ABA = 5

#: AS PROVAS SÃO LITERAIS, E É ESCOLHA — a tentação era montá-las chamando o
#: mesmo `_plano()` que o gesto chama, para "não digitar o que tem dono". Isso
#: teria custado as duas coisas que uma régua existe para dar:
#:
#:   1. **a régua viraria tautologia.** Os dois lados perguntariam ao mesmo
#:      `plan_mode_transition`, e um gesto que passasse a chave ERRADA (o chip
#:      Xbox pedindo a máscara `dualsense`) daria verde nos dois lados;
#:   2. **o pacote deixaria de ser puro.** `PROVAS` é lido no IMPORT, e montá-lo
#:      com `_plano()` puxaria `painel` → `home_actions` → GTK para dentro do
#:      import das dez abas — o contrário do que `_painel()` existe para evitar.
#:
#: O preço, declarado: se o produto mudar a sequência de um modo, ESTA LISTA
#: reprova. É o preço certo — é a régua avisando que a definição do modo se
#: moveu, que é exatamente a notícia que se quer ter.
#:
#: `origin="manual"` aparece em todo passo que DEFINE modo, e não é enfeite: sem
#: ele o daemon lê o pedido como reconciliação automática e o recusa quando há
#: Steam Input na jogada (ORIGEM-QUE-MENTE-01, medido na máquina dela — o botão
#: "Jogar pelo Hefesto" parou de funcionar com o Sackboy marcado).
_MANUAL_ON = {"enabled": True, "origin": "manual"}
_MANUAL_OFF = {"enabled": False, "origin": "manual"}

PROVAS = [
    # LIGADO: sai do Modo Nativo e SÓ ENTÃO liga o gamepad. Invertidos, o vpad
    # nasceria com o físico ainda grabado pelo jogo (HARM-01).
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "gamepad"},  # (noqa-acento) id
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_ON)]},
    # DESLIGADO é o Modo Nativo, e é UM passo só — decisão dela, 31/08.
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "native"},  # (noqa-acento) id
     "chama": [("chamar", ["native.mode.set"], _MANUAL_ON)]},
    # O CHIP MUDA A MÁSCARA, NÃO O MODO: o `flavor` é a única diferença entre
    # este e o Xbox logo abaixo. Ele sai de `painel.CHIPS_DA_ESCADA`, não é
    # digitado no gesto — o que está digitado aqui é a EXPECTATIVA.
    {"pagina": PAGINA, "gesto": "modo-dualsense", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "flavor": "dualsense"})]},
    {"pagina": PAGINA, "gesto": "modo-xbox", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "flavor": "xbox"})]},
    # TRÊS, e o terceiro é o que separa "entrei no modo" de "entrei num modo sem
    # função": `mouse.emulation.restore` liga o mouse conforme a preferência
    # persistida (HARM-06), e vem POR ÚLTIMO de propósito.
    {"pagina": PAGINA, "gesto": "modo-navegacao", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_OFF),
               ("chamar", ["mouse.emulation.restore"], {})]},
    # RECONCILIAR ANTES DE RENUMERAR: renumerar primeiro compactaria uma mesa
    # que ainda não está completa (`home_actions.py:3122`).
    {"pagina": PAGINA, "gesto": "reconectar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["coop.sync"], {}),
               ("chamar", ["identity.renumber"], {})]},
]
