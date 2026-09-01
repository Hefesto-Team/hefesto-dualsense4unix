#!/usr/bin/env python3
"""O pacote da aba `08` Conexões.

O QUE TEM DONO: a contagem da mesa por transporte, e é o que o cabeçalho desta
aba promete (`2 na mesa · 1 no cabo · 1 no rádio`). Sai de `controllers[]`, e a
mesma regra das outras: conta os CONECTADOS.

O EXAME NÃO TEM DONO NO `state_full`, e é honesto dizer por quê: as cinco linhas
do Check-up saem do `doctor`, que é outro programa e responde por outro caminho.
Elas não são estado do daemon — são o resultado de um exame que alguém mandou
rodar. Pintá-las do `state_full` seria inventar.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. Aqui estavam "exame" e "adaptadores" como órfãos.
#: Os dois têm dono, e são os mesmos que a `gui/aba_conexoes.py` dela usa hoje:
#: `integrations/exame_da_mesa` devolve os itens do exame prontos, e
#: `integrations/radio_da_mesa.ocupacao_por_adaptador` diz quem está em qual
#: adaptador. Perguntar só ao `state_full` foi o erro.
SEM_DONO: dict[str, str] = {}


def _exame() -> list[dict]:
    """Os itens do exame da mesa, do mesmo módulo que a GUI dela usa.

    ELE TOCA O SISTEMA (`busctl`, sysfs), logo pode demorar ou falhar — e uma
    falha aqui NÃO pode derrubar a aba. A lista vazia é um estado legítimo
    ("nada a apontar"); a exceção vira lista vazia com o motivo ao lado, para
    que a tela não confunda "examinei e está tudo bem" com "não consegui
    examinar" — que é o defeito que esta casa chama de *ausência de notícia
    lida como sucesso*.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations import exame_da_mesa

        itens = []
        for fn in ("energia_do_radio", "energia_das_portas", "suporte_ao_controle"):
            f = getattr(exame_da_mesa, fn, None)
            if f is None:
                continue
            try:
                r = f()
            except Exception:
                continue
            for it in (r if isinstance(r, (list, tuple)) else [r]):
                if it is None:
                    continue
                # OS CAMPOS SÃO `rotulo`, `estado` e `porque` — os do
                # `exame_da_mesa.Item`, lidos do dataclass. A primeira versão
                # daqui pedia `titulo` com `or str(it)` de reserva, e o `Item`
                # não tem `titulo`: a reserva ganhava sempre e o **`repr` do
                # objeto Python foi parar na tela dela**, visível na foto de
                # 01/09 — `Item(chave='energia_do_radio', rotulo='Economia de
                # energia desligada', estado='a`, cortado no meio.
                #
                # Um `getattr` com reserva é o disfarce perfeito para um campo
                # que não existe: ele não levanta, e o que sai parece dado.
                estado = str(getattr(it, "estado", "") or "")
                itens.append({
                    "chave": getattr(it, "chave", fn),
                    "titulo": str(getattr(it, "rotulo", "") or ""),
                    "porque": str(getattr(it, "porque", "") or ""),
                    "estado": estado,
                    # `certo` é o único estado que não pede nada — os outros
                    # (`ajustar`, `atencao`) são achados de verdade.  # noqa-acento
                    "grave": estado.lower() not in {"certo", ""},
                })
        return itens
    except Exception:
        return []


def _adaptadores(conectados) -> dict:
    """Quem está em qual adaptador de rádio.

    O MAC NÃO SAI DAQUI CRU para lugar nenhum que se grave: este pacote devolve
    para a tela em memória, e a máscara da casa (octetos 4 e 5 zerados) é o que
    vai para qualquer relato. São dois portões nesta árvore e eles não perdoam.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations import radio_da_mesa

        ocup = radio_da_mesa.ocupacao_por_adaptador([c.get("uniq") for c in conectados])
        return {str(k): v for k, v in (ocup or {}).items()}
    except Exception:
        return {}


@registrar("08-conexoes.html")
def pacote(ctx: Contexto) -> dict:
    st = ctx.state
    itens = _exame()
    adap = _adaptadores(ctx.conectados)

    colunas = {}
    for c in ctx.conectados:
        colunas[str(c.get("uniq") or "")] = {
            "via": (c.get("transport") or "").upper(),
            "bateria": c.get("battery_pct"),
            "ponte": bool(c.get("uniq") in (st.get("pontes_confirmadas") or {})),
            "fragil": bool(c.get("uniq") in (st.get("native_bt_fragil_controles") or [])),
        }
    return {
        "colunas": colunas,
        # AS DUAS LISTAS SÃO O QUE A TELA MOSTRA, uma por bloco de achado: o
        # selo (CERTO/AJUSTAR) e a frase. Elas se distribuem pelos elementos de
        # mesmo `data-campo`, na ordem — o gerador não precisa saber quantos
        # achados o exame vai devolver.
        "selo": ["AJUSTAR" if i["grave"] else "CERTO" for i in itens],
        "achado": [i["titulo"] for i in itens],
        "exame": itens,
        "achados": len(itens),
        "graves": sum(1 for i in itens if i["grave"]),
        "adaptadores": adap,
        "sem_driver": st.get("controles_sem_driver") or [],
        "sem_dono": {},
        "cobertura": {"pintados": 4 + len(itens) + len(adap)
                      + sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao daemon
# ---------------------------------------------------------------------------
# ESTA ABA É A DE MAIS BOTÕES DAS DEZ — 56 elementos ganharam `data-gesto` no
# gerador — E A DE MENOS DONOS. O número não é vergonha: é o inventário. A razão
# está medida botão a botão em `SEM_GESTO`, aqui embaixo, e ela se resume a três
# formas:
#
#   1. **o gesto não é IPC.** "A luz não acende" é `Disconnect` do BlueZ pelo
#      D-Bus (`integrations/gesto_de_reconexao.py`), "Examinar Portas" é
#      `integrations/exame_da_mesa` (sysfs + `busctl`), e "Renomear" é o
#      `org.bluez.Adapter1.Alias` (`integrations/apelido_do_dongle.py:481`).
#      Nenhum dos três passa pelo daemon, e o `ponte.py` é a ponte para o
#      daemon. Ligá-los daqui seria abrir um segundo caminho de escrita.
#   2. **o piloto só ouve `click`.** `hefesto_vivo.py:188` instala UM ouvinte, e
#      é de `click`. Um `<select>` do WebKitGTK abre popup nativo: o clique que
#      chega é o de ABRIR, e o valor que ele carrega é o ANTIGO. Ligar um select
#      aqui aplicaria a escolha anterior a cada abertura — que é pior que não
#      responder. São seis campos nesse caso, e um deles (`vizinho-o-que-e`) tem
#      dono no daemon esperando por um ouvinte de `change`.
#   3. **o dado da tela é do MOCKUP, não da mesa dela.** A pop-up "Mapear
#      Entradas" desenha `CENSO`, `FACES` e `QUEM_ESTA` — constantes do gerador.
#      Nenhuma delas é repintada pelo pacote. Um `machine.declare` disparado
#      dali gravaria no `maquina.json` DELA um mapa derivado de uma bancada de
#      exemplo. É o defeito mais caro que esta aba poderia cometer, porque o
#      arquivo que ele estragaria é o único que guarda o que só ela sabe.
from . import gesto  # noqa: E402

#: O QUE FOI MARCADO E **NÃO** FOI LIGADO, com o motivo medido de cada um. Esta
#: lista não é lápide: o piloto imprime `[gesto sem dono] 08-conexoes.html · X`
#: a cada clique nesses botões, e é assim que o que falta aparece na tela em vez
#: de sumir. Quem ligar um deles tira a linha daqui.
SEM_GESTO: dict[str, str] = {
    "luz-nao-acende":
        "`Disconnect` do BlueZ pelo D-Bus — `integrations/gesto_de_reconexao.py`, "
        "que roda `busctl` e não passa pelo daemon. Não há método IPC para isto.",
    "examinar-portas":
        "o exame é `integrations/exame_da_mesa` (sysfs + `busctl`), não IPC. E ele "
        "já roda a cada tique dentro de `_exame()` aqui em cima — o botão pediria "
        "de novo o que a aba refaz duas vezes por segundo.",
    "ignorar":
        "dispensar uma ordem grava `mesa.ordens_dispensadas[chave] = {quando, "
        "arranjo}` (`secao_exame.py:995`), e a CHAVE E O ARRANJO são de um "
        "`ordens_da_mesa.Ordem`. As linhas do exame desta aba saem de "
        "`exame_da_mesa.Item`, e só têm `ordem` quando a linha É uma ordem — as "
        "três que `_exame()` traz hoje não são. Gravar com `arranjo=\"\"` passaria "
        "no esquema e NÃO calaria nada: `ordens_da_mesa.py:850` compara o arranjo "
        "guardado com o de agora, e nunca casaria. Botão que grava e não cala.",
    "mic-existe":
        "TEM dono no daemon (`mic.set`, `ipc_bridge.mic_set(muted, uniq)`, o mesmo "
        "que o `controller_card.py:3562` chama) e não tem ouvinte: é `<select>`, e "
        "o piloto só escuta `click`.",
    "mic-escopo":
        "é `mic_button_toggles_system`, e o produto guarda UM por máquina "
        "(`daemon/lifecycle.py:272`), aplicado pelo rascunho do perfil "
        "(`ipc_draft_applier.py:592`) — não por controle, que é o que a tela "
        "oferece. A contradição está declarada em `gui/aba_conexoes.SEM_FONTE`.",
    "teto-da-vibracao":
        "a tela oferece um teto POR CONTROLE e o produto aplica `min` global "
        "(`core/rumble.py`) — `gui/aba_conexoes.SEM_FONTE` diz que sobrepor mudaria "
        "o daemon, não a tela. E é `<select>`, sem ouvinte de `change`.",
    "vizinho-o-que-e":
        "TEM dono (`machine.declare`, `mesa.radios[vid:pid].tipo` — "
        "`secao_mesa._ao_declarar_o_radio:1486`) e não tem ouvinte: é `<select>`. "
        "É o único desta aba que só espera um `change` no `hefesto_vivo.py`.",
    "escolher-aparelho":
        "a lista de aparelhos é a constante `CENSO` do gerador, não o censo do "
        "barramento dela. Escolher aqui é um dos dois tempos de um gesto que só "
        "termina na entrada, e nenhum dos dois lados é dado vivo.",
    "escolher-entrada":
        "os quadrados saem de `FACES`/`QUEM_ESTA`, constantes do gerador. Declarar "
        "`mapa.portas` a partir deles escreveria no `maquina.json` dela o desenho "
        "de uma bancada de exemplo.",
    "nova-entrada": "mesma razão de `escolher-entrada`: a face é do mockup.",
    "novo-hub": "mesma razão — e o hub ainda pergunta em que entrada está.",
    "tirar-daqui": "mesma razão: o alvo é um quadrado do mockup.",
    "nova-extensao": "mesma razão: a mãe é um quadrado do mockup.",
    "nova-face":
        "o nome sai de um `<input>`, e o ouvinte do piloto manda `texto` = o "
        "`textContent` do BOTÃO, nunca o `value` do campo (`hefesto_vivo.py:208`). "
        "O gesto chegaria sem o nome — e sem nome, o produto não cria.",
}


def _uniq(o: dict) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa.

    O piloto traduz `pref` → `uniq` antes de chamar (`hefesto_vivo.py:337`); o
    que chega aqui vazio é clique sem dono, e "" NÃO vira "o primeiro".
    """
    return str(o.get("uniq") or "")


def _indice(ctx: Contexto, uniq: str) -> int | None:
    """A posição daquele controle em `controllers` — o que o daemon numera.

    **NÃO é o número do jogador.** `controller.target.set` pede `index`, "posição
    em `controllers`, 0 = primário" (`ipc_handlers.py:4130`), e o próprio produto
    já separa as duas coisas: `status_actions._controller_target_rows:1579` ORDENA
    a lista pelo número de identidade e CARREGA em cada linha o `index` da
    enumeração, com o comentário dizendo por quê — *"a usuária clicaria no chip do
    1 e editaria outro controle"*.

    O `index` vem publicado por entrada (é o mesmo campo que
    `ipc_handlers._numero_de_exibicao:526` lê). Quando ele falta, a posição na
    lista `controllers` é a MESMA conta — e `None` quando nem isso: aí o gesto
    recusa dizendo, em vez de mirar o 0 e trocar o controle dela.
    """
    dele = ctx.por_uniq(uniq)
    i = dele.get("index")
    if isinstance(i, int) and not isinstance(i, bool):
        return i
    lista = ctx.state.get("controllers") or ctx.conectados
    for posicao, c in enumerate(lista):
        if str(c.get("uniq") or "") == uniq:
            return posicao
    return None


def _resposta(r) -> tuple[bool, str]:
    """`(ok, motivo)` do `machine_declare`, tolerando ponte que devolva só `bool`.

    `ipc_bridge.machine_declare:861` devolve `(ok, motivo)`, e o motivo já vem
    traduzido para frase de tela (`_MOTIVOS_MAQUINA`) — é ele que faz o botão
    RECUSAR DIZENDO em vez de gravar calado.

    O guarda existe porque o dublê da régua
    (`tests/unit/test_os_botoes_tem_dono.PonteDeMentira`) devolve `True` para todo
    nome que não seja `identity…_set`: desempacotar às cegas levantaria
    `TypeError` DENTRO do teste, e o instrumento reprovaria a si mesmo em vez de
    medir o botão.
    """
    if isinstance(r, tuple):
        ok, motivo = [*r, None, None][:2]
        return bool(ok), str(motivo or "")
    return bool(r), ""


def _declarar(p, mesa: dict) -> None:
    """Grava um pedaço da declaração da mesa, na hora.

    DECISÃO DELA, 01/09/2026: **clicar já aplica** — a interface nova não junta
    mudanças num rascunho à espera de um "Aplicar". A GUI estável faz o
    contrário de propósito (`secao_mesa._ao_declarar:1467` acumula em
    `_maquina_pendente` e o rodapé grava), e o motivo dela — *"chamar
    `machine.declare` daqui criaria um segundo dono do gesto de gravar"* — vale
    para AQUELA janela, que tem um rodapé que grava. Aqui o dono do gesto é o
    clique.

    A DECLARAÇÃO É PARCIAL, e é o que torna isto seguro: o daemon funde contra o
    disco sob lock (`ipc_handlers._handle_machine_declare:5254`), então mandar
    `{"mesa": {"altura_da_antena": …}}` não apaga `linha_de_visada`, nem os
    rádios, nem o mapa do gabinete.
    """
    ok, motivo = _resposta(p.machine_declare({"mesa": mesa}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o que você declarou")


@gesto("08-conexoes.html", "alvo")
def alvo(ctx: Contexto, o: dict, p) -> None:
    """"Só este": as ações de saída passam a mirar SÓ este controle.

    É o que a própria tela promete no `title` das três etiquetas que abrem a
    linha do acordeão: *"Deixa só este controle aberto — os outros fecham. A
    fita do topo passa a apontar para ele."*

    `controller.target.set` é exatamente isso, e o handler diz com todas as
    letras (`daemon/ipc_handlers.py:4132`): *"Com o alvo setado,
    lightbar/gatilhos/player-LED/rumble/mic-LED passam a mirar SÓ aquele
    controle"*. É o mesmo método que o seletor da GUI estável chama
    (`app/actions/status_actions.py:2453`).

    ELE NÃO TEM FUNÇÃO NO `ipc_bridge` — é o degrau 3 da ponte, e passa pelo
    mesmo `_safe_call`, com o mesmo timeout.

    O QUE ESTE GESTO **NÃO** FAZ, e é honesto dizer: a fita do topo não se move.
    O piloto único chama `mesa_viva.mesa_do_estado(st, …)` sem o argumento `alvo`
    (`hefesto_vivo.py:476`), então a fita aponta sempre para a posição 1. Quem
    mudar isso é o piloto, não este pacote — o efeito que ESTE gesto entrega é o
    do daemon, e ele é real.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("alvo: o clique não disse em qual controle")
    indice = _indice(ctx, uniq)
    if indice is None:
        raise RuntimeError(
            "alvo: este controle não está na lista do daemon — sem posição, "
            "mirar o 0 trocaria o controle debaixo da mão dela")
    p.chamar("controller.target.set", index=indice)


@gesto("08-conexoes.html", "todos")
def todos(ctx: Contexto, o: dict, p) -> None:
    """"▴": volta ao broadcast — as ações voltam a valer para a mesa inteira.

    O `title` do botão é o contrato: *"Fecha — a fita volta para 'Todos', e os N
    controles abrem juntos."* No daemon, "Todos" é `index: null`
    (`ipc_handlers.py:4134`: *"`index` null volta ao broadcast (padrão)"*), e é o
    mesmo `None` que a linha 0 do seletor da GUI estável carrega
    (`status_actions._controller_target_rows:1586`).

    ELE NÃO PRECISA DO `uniq`, e é o único desta aba assim: "todos" não tem
    sujeito. Exigir um aqui deixaria a saída presa no último controle escolhido
    sempre que ela fechasse a linha pela seta, que é o gesto mais comum.
    """
    p.chamar("controller.target.set", index=None)


@gesto("08-conexoes.html", "sala-altura")
def sala_altura(ctx: Contexto, o: dict, p) -> None:
    """"O dongle fica acima da cabeça de quem joga sentado?" — grava a resposta.

    É uma das duas coisas que barramento nenhum responde, e por isso ela é
    DECLARADA: `MesaDeclarada.altura_da_antena` (`utils/maquina.py:277`), que só
    aceita `"acima"`, `"abaixo"` ou `None`.

    QUEM CONSOME: `exame_da_mesa.vizinhanca_das_portas` recebe
    `altura_da_antena` e muda o que o Check-up desta MESMA aba diz. A resposta
    não é enfeite de formulário — ela troca a linha do exame.

    O `data-modo` traz o id do esquema, e `""` é "Não sei" → `None`. A conversão
    tem de ser aqui: a string `"nao_sei"` faria o pydantic recusar o documento
    INTEIRO (`extra="forbid"` + `Literal`), e o sintoma na tela seria "não
    consegui gravar" em vez de "valor inválido" — é a mesma razão escrita em
    `secao_mesa._valor_do_seletor:1498`.
    """
    escolha = str(o.get("modo") or "")
    if escolha not in ("acima", "abaixo", ""):
        raise ValueError(f"sala-altura: {escolha!r} não é resposta desta pergunta")
    _declarar(p, {"altura_da_antena": escolha or None})


@gesto("08-conexoes.html", "sala-visada")
def sala_visada(ctx: Contexto, o: dict, p) -> None:
    """"Tem gente sentada entre o dongle e o sofá?" — grava a resposta.

    O par da de cima: `MesaDeclarada.linha_de_visada` (`utils/maquina.py:278`),
    `"com_gente"` / `"livre"` / `None`. Corpo humano absorve 2,4 GHz e nenhum
    barramento sabe disso — é o que o cabeçalho do `utils/maquina.py` chama de "o
    que nenhum barramento sabe".

    SEPARADO DA ALTURA, E NÃO UM GESTO SÓ COM DUAS CHAVES: são duas perguntas, e
    responder uma não é responder a outra. Um gesto único teria de mandar as duas
    chaves a cada clique, e a chave não respondida iria como `None` — que na
    fusão é uma ESCOLHA ("voltei para 'Não sei'"), não uma ausência
    (`utils/maquina.fundir_declaracao:650`). Responder "Sim" na altura apagaria a
    visada, calado.
    """
    escolha = str(o.get("modo") or "")
    if escolha not in ("com_gente", "livre", ""):
        raise ValueError(f"sala-visada: {escolha!r} não é resposta desta pergunta")
    _declarar(p, {"linha_de_visada": escolha or None})


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
PONTE = {"chamar", "machine_declare"}
METODOS = {"controller.target.set"}


#: O QUE ESTA ABA DECLARA À RÉGUA — o piso e as provas moram AQUI, e não no
#: teste, para que ligar uma aba não exija editar um arquivo que oito pessoas
#: editariam ao mesmo tempo.
PAGINA = "08-conexoes.html"
PISO_DA_ABA = 4
PROVAS = [
    # O `index` da prova é 0 porque o controle de mentira é o único da lista —
    # e o `_indice` cai na posição quando o daemon não publicou `index`.
    {"pagina": PAGINA, "gesto": "alvo", "clique": {},
     "chama": [("chamar", ["controller.target.set"], {"index": 0})]},
    # SEM `uniq` no clique de propósito: "todos" não tem sujeito, e a régua
    # prova que ele não passa a exigir um.
    {"pagina": PAGINA, "gesto": "todos", "clique": {"uniq": "", "controle": ""},
     "chama": [("chamar", ["controller.target.set"], {"index": None})]},
    {"pagina": PAGINA, "gesto": "sala-altura", "clique": {"modo": "acima"},
     "chama": [("machine_declare", [{"mesa": {"altura_da_antena": "acima"}}], {})]},
    # "Não sei" chega como `""` e tem de virar `None` — a string `"nao_sei"`
    # derrubaria o documento inteiro no pydantic.
    {"pagina": PAGINA, "gesto": "sala-visada", "clique": {"modo": ""},
     "chama": [("machine_declare", [{"mesa": {"linha_de_visada": None}}], {})]},
]

#: OS DOIS QUE GRAVAM NO DISCO, e não no daemon. "O dongle fica acima da
#: cabeça?" e "há parede entre o dongle e quem joga?" são coisas que barramento
#: nenhum responde — são DECLARADAS, e vão para `MesaDeclarada` no
#: `maquina.json` (`utils/maquina.py`). O `state_full` não as republica.
#:
#: A prova deles é o ARQUIVO, não o estado: quem consome é o
#: `exame_da_mesa.vizinhanca_das_portas`, que muda a linha do Check-up desta
#: mesma aba. Uma régua que só olhasse o daemon diria "sem efeito" sobre um
#: botão que trocou o diagnóstico da tela.
SEM_ECO = ("sala-altura", "sala-visada")
