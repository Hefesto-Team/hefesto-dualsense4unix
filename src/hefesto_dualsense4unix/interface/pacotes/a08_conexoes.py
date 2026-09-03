#!/usr/bin/env python3
"""O pacote da aba `08` Conexões.

O QUE TEM DONO: a contagem da mesa por transporte, e é o que o cabeçalho desta
aba promete (`2 na mesa · 1 no cabo · 1 no rádio`). Sai de `controllers[]`, e a
mesma regra das outras: conta os CONECTADOS.

O EXAME NÃO TEM DONO NO `state_full`, e é honesto dizer por quê: as linhas do
Check-up saem do `integrations/exame_da_mesa`, que lê o sistema por outro
caminho. Elas não são estado do daemon — são o resultado de um exame que alguém
mandou rodar. Pintá-las do `state_full` seria inventar.

ESTA ABA TEM TRÊS FONTES, E É O QUE A TORNA DIFERENTE DAS OUTRAS NOVE:

    state_full          o daemon, a 500 ms — a mesa, o transporte, a bateria
    maquina.json        a DECLARAÇÃO dela — o que barramento nenhum responde
    /sys + busctl       o exame e os rádios vizinhos — lidos SOB DEMANDA

As duas últimas não estão no tique de propósito, e a razão está medida no bloco
"O QUE SE LÊ DA MÁQUINA, E QUANDO", logo abaixo. É essa separação que dá
trabalho de verdade ao botão **Examinar Portas** — e é ela que faz o ⊘ de cada
linha do Check-up ter um sujeito para calar.
"""
from __future__ import annotations

import contextlib
import dataclasses as _dataclasses
import time
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

from . import Contexto, perfil, registrar

if TYPE_CHECKING:
    # SÓ PARA O MYPY, e por isso não é uma exceção à regra do import tardio: em
    # tempo de execução esta linha não roda, então nada resolve contra a árvore
    # errada. O que ela compra é o mypy conferindo os quatro campos da
    # `Vibracao` — que é justamente onde o defeito nasceu, com dois `str | None`
    # trocados de posição em silêncio.
    from hefesto_dualsense4unix.gui.aba_conexoes import Vibracao

#: CORRIGIDO EM 01/09/2026. Aqui estavam "exame" e "adaptadores" como órfãos.
#: Os dois têm dono, e são os mesmos que a `gui/aba_conexoes.py` dela usa hoje:
#: `integrations/exame_da_mesa` devolve os itens do exame prontos, e
#: `integrations/radio_da_mesa.ocupacao_por_adaptador` diz quem está em qual
#: adaptador. Perguntar só ao `state_full` foi o erro.
SEM_DONO: dict[str, str] = {}


# ---------------------------------------------------------------------------
# O QUE SE LÊ DA MÁQUINA, E QUANDO — a regra é do produto, não minha
# ---------------------------------------------------------------------------
# `mesa_de_radio.ler_a_mesa` diz, no próprio docstring: *"Chamada ao ENTRAR na
# aba e no botão 'Reexaminar a mesa', **nunca em tique** — os tiques desta casa
# são de 100 ms, 500 ms e 2 s, e pendurar uma varredura de barramento em
# qualquer um deles é gastar CPU para reler o que não muda."* O tique deste
# piloto é de 500 ms, então o que varre barramento é LIDO UMA VEZ e guardado
# aqui; quem o renova é o botão **Examinar Portas**, que é exatamente o que ele
# promete no `title`.
#
# MEDIDO NESTA MÁQUINA, em 01/09/2026, para saber o que cabia no tique e o que
# não cabia:
#
#     ler_a_mesa()                          0,001 s   listdir de /sys, sem fork
#     exame(leitura_das_ordens=...)         0,02  s   MAS forka `busctl`
#
# Os 20 ms caberiam. O `busctl` é que não: `_busctl` tem teto de 5 s
# (`exame_da_mesa.ESPERA_DO_BUSCTL_S`), e um fork por meio segundo contra o
# BlueZ é um preço que a tela não paga por estar aberta. Por isso o exame
# COMPLETO — as cinco conferências e as ordens de serviço — é do botão, e o
# tique fica com as três conferências que não forkam nada.
#
# O ESTADO AQUI É DE MÓDULO, e não do `Contexto`: o `Contexto` é remontado a
# cada tique pelo piloto e não tem onde guardar uma leitura entre um tique e o
# seguinte. Escrever é uma atribuição de tupla/dicionário novo — o tique lê, o
# gesto (que roda em thread) escreve, e nenhum dos dois vê metade de nada.

#: A declaração dela, do `maquina.json`. Lida uma vez e renovada pelos gestos
#: que a mudam — ler o disco duas vezes por segundo para pintar dois `<select>`
#: seria o mesmo desperdício que a regra acima proíbe.
_DECLARACAO: object | None = None

#: Os rádios vizinhos, na ordem em que `ler_a_mesa` os devolve. É esta ordem que
#: o desenho pinta e é ela que o `data-v` de cada `<select>` endereça.
_MESA_DO_RADIO: object | None = None

#: `vid:pid` por POSIÇÃO no desenho — o que estava no slot N quando o último
#: tique pintou. É a ponte entre o clique (que só sabe dizer "o terceiro") e o
#: `maquina.json` (que só sabe endereçar por `vid:pid`).
_VIZINHOS: tuple[str, ...] = ()

#: O que só o exame COMPLETO traz: `pareamentos`, `vizinhanca_das_portas` e as
#: ordens de serviço. Vazio até ela clicar em **Examinar Portas**.
_EXTRAS: tuple[object, ...] = ()

#: A ordem de serviço de cada POSIÇÃO da tira do exame, ou `None` quando aquela
#: linha é uma conferência (que não se dispensa). Mesma ponte do `_VIZINHOS`.
#: `Any` E NÃO `object`: o que mora aqui é a `ordem` que o exame da mesa
#: devolve, com `.chave` e `.arranjo`. `object` não tem atributo nenhum, e
#: então o `ignorar` que os lê não passava no `mypy` — a anotação estava
#: dizendo menos do que se sabe sobre o valor.
_ORDENS_NA_TELA: tuple[Any | None, ...] = ()

#: QUANDO O EXAME COMPLETO CORREU, em `time.monotonic()`, ou `None` enquanto o
#: botão **Examinar Portas** não foi clicado nesta sessão. É o relógio do
#: carimbo "Examinado …" do topo do Check-up — ver `_carimbo_do_exame`.
_QUANDO_O_EXAME: float | None = None

#: `{chave da regra: arranjo dispensado}` — o que a decisão dela está segurando.
#: Sai do disco e é atualizado NA HORA pelo `ignorar`: sem isso a linha voltaria
#: no tique seguinte, e um botão que grava e não cala é o defeito que este
#: pacote mediu em 01/09 como razão para NÃO ligá-lo.
_DISPENSADAS: dict[str, str] = {}


def _declaracao(recarregar: bool = False) -> Any:
    """O `maquina.json` já validado, ou `None` se não deu para ler.

    `carregar_maquina` **nunca levanta** — no pior caso devolve o documento
    todo em "não sei" —, então o `None` daqui só acontece se o import falhar,
    que é o caso de uma árvore sem `src/`.
    """
    global _DECLARACAO
    if _DECLARACAO is None or recarregar:
        try:
            perfil._com_o_src()
            from hefesto_dualsense4unix.utils.maquina import carregar_maquina

            _DECLARACAO = carregar_maquina()
        except Exception:
            return None
    return _DECLARACAO


def _mesa_do_radio(recarregar: bool = False) -> Any:
    """Adaptadores e rádios vizinhos, lidos do `/sys` — uma vez, e no botão.

    Devolve `None` quando a varredura falhou, e o `None` é diferente de uma
    mesa vazia: "não medi" não pode virar "não há rádio nenhum", que é a
    ausência de notícia lida como sucesso.
    """
    global _MESA_DO_RADIO
    if _MESA_DO_RADIO is None or recarregar:
        try:
            perfil._com_o_src()
            from hefesto_dualsense4unix.integrations import mesa_de_radio

            _MESA_DO_RADIO = mesa_de_radio.ler_a_mesa()
        except Exception:
            return None
    return _MESA_DO_RADIO


#: O CENSO DO BARRAMENTO, lido UMA vez e renovado pelo "Examinar Portas" — a
#: mesma regra do `_mesa_do_radio` acima, e pelo mesmo motivo: é varredura de
#: `/sys`, e o tique desta aba é de 500 ms.
_CENSO: Any = None


def _censo(recarregar: bool = False) -> Any:
    """Tudo que o barramento tem, para o motor julgar as entradas.

    `None` quando a leitura falhou, e ele é diferente de um censo VAZIO: sem
    censo o motor não julga, e o mapa mostra as entradas sem veredito — o que é
    honesto. Um censo vazio faria toda entrada parecer livre.
    """
    global _CENSO
    if _CENSO is None or recarregar:
        try:
            perfil._com_o_src()
            from hefesto_dualsense4unix.integrations.censo_do_barramento import (
                ler_o_barramento,
            )

            _CENSO = ler_o_barramento()
        except Exception:
            return None
    return _CENSO


def _logica_do_mapa() -> Any:
    """O rascunho do gabinete DELA — `LogicaDoMapa` sobre o que ela declarou.

    ELE É O ESTADO DOS SEIS BOTÕES do mapa. `LogicaDoMapa` é a camada do produto
    que já existia e que tela nenhuma tinha chamado: ela guarda as faces, as
    entradas e o aparelho na mão, e tem os quatro gestos que os mudam
    (`acrescentar_entrada`, `acrescentar_face`, `acrescentar_extensao`,
    `colocar`/`tirar`). Sem GTK — o próprio docstring dela diz por quê.

    NÃO SE RECRIA A CADA TIQUE, e a razão é o `escolhido`: o gesto de dois
    tempos ("clique no aparelho, depois na entrada") guarda o primeiro tempo
    AQUI. Reconstruir do disco a cada pintura apagaria o aparelho da mão dela
    entre um clique e outro.
    """
    global _LOGICA
    if _LOGICA is None:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import LogicaDoMapa
        from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

        declarada = _declaracao()
        mapa = getattr(declarada, "mapa", None) or MapaDaMesa()
        _LOGICA = LogicaDoMapa(mapa)
    return _LOGICA


#: O rascunho vivo. `None` = ainda não montado.
_LOGICA: Any = None


def _chave_do_radio(r: Any) -> str:
    """`vid:pid` — a chave do `maquina.json`, e não o nó do sysfs.

    A razão é do produto e está escrita em `secao_mesa._ao_declarar_o_radio`: o
    nó muda de nome quando o aparelho troca de porta, e a resposta *"isto é um
    teclado"* não muda com a porta.
    """
    return f"{getattr(r, 'vid', '')}:{getattr(r, 'pid', '')}"


def _tipos_de_radio() -> tuple[dict[str, str], dict[str, str]]:
    """`(rótulo → id, id → rótulo)` das respostas do "— O que é? —".

    OS DOIS SAEM DO PRODUTO (`secao_mesa._TIPOS_DE_RADIO`), e é o mesmo par que
    a GUI estável usa no seletor dela. A tela manda o RÓTULO ("Caixa de som") e
    o esquema exige o id (`caixa_de_som`, `Literal` em `RadioDeclarado.tipo`):
    mandar o rótulo faria o pydantic recusar o DOCUMENTO INTEIRO, e o sintoma
    na tela seria "não consegui gravar" em vez de "valor inválido".
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_mesa import _TIPOS_DE_RADIO

        return ({rotulo: ident for ident, rotulo in _TIPOS_DE_RADIO},
                dict(_TIPOS_DE_RADIO))
    except Exception:
        return {}, {}


def _a_pergunta() -> str:
    """A primeira opção do "— O que é? —" — a pergunta em si.

    Ela sai de `gui/aba_conexoes.RESPOSTAS_DO_VIZINHO`, que é a camada de tela
    DESTA aba e é a mesma lista que o gerador usa desde 01/09. Enquanto essa
    opção estiver escolhida, o produto NÃO sabe o que aquele rádio é, e a tela
    diz isso em vez de chutar.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.gui.aba_conexoes import RESPOSTAS_DO_VIZINHO

        return str(RESPOSTAS_DO_VIZINHO[0])
    except Exception:
        return ""


def _mesa_declarada(declaracao: Any) -> dict[str, Any]:
    """As duas respostas que barramento nenhum dá: a altura e a visada.

    Elas alimentam `exame_da_mesa.vizinhanca_das_portas`, e é o que fecha o laço
    dos gestos `sala-altura` e `sala-visada`: o que ela declarou muda a linha do
    Check-up desta MESMA aba.
    """
    try:
        mesa = declaracao.mesa
        return {"altura_da_antena": mesa.altura_da_antena,
                "linha_de_visada": mesa.linha_de_visada}
    except Exception:
        return {}


def _radios_declarados(declaracao: Any) -> dict[str, str]:
    """`{vid:pid: tipo}` — o que ela já respondeu sobre cada rádio vizinho."""
    try:
        return {str(k): str(v.tipo or "")
                for k, v in (declaracao.mesa.radios or {}).items()}
    except Exception:
        return {}


def _mic_declarado(declaracao: Any, uniq: str) -> bool:
    """A ponte de microfone DESTE controle está declarada?

    **Só `True` conta**, e é regra do produto (`bt_mic.uniqs_declarados`):
    ausência e `False` deixam a ponte no chão do mesmo jeito. Ler `False` como
    "desligado" e ausência como "não sei" daria à tela um terceiro estado que o
    produto não tem.
    """
    try:
        chave = _so_hex(uniq)
        declarado = (declaracao.controles or {}).get(chave)
        return getattr(declarado, "microfone", None) is True
    except Exception:
        return False


def _so_hex(uniq: str) -> str:
    """`d4:2f:…` → `d42f…` — a forma que o `maquina.json` exige por schema.

    A CONTA É DO PRODUTO — `core.sysfs_leds.norm_mac`, o dono da chave —, e esta
    função é só o embrulho que devolve `""` no lugar do `None` dele: as três
    chamadas daqui usam o resultado como chave de dicionário e como pedaço de
    texto, e um `None` viraria a chave `None` ou a palavra `"None"` numa frase.
    A `a02_controles` já tinha migrado (`:305`); esta era a segunda grafia.

    O QUE MUDA, MEDIDO em 02/09/2026 sobre oito entradas: **nada** no que esta
    aba recebe. As duas versões dão o mesmo resultado nas quatro formas de MAC
    (`d4:2f:…`, `D4-2F-…`, com espaço em volta, e já sem separador) e no vazio.
    Elas só divergem sobre texto que não é MAC — `"usb-0000:00:14.0-3"` virava
    `"usb00000014.03"` aqui e vira `"b0000001403"` no dono —, e nenhuma das
    duas formas casa com uma chave do `maquina.json`: as duas erram, e errar de
    um jeito só é o ponto.
    """
    return norm_mac(uniq) or ""


def _dispensadas_do_disco(declaracao: Any) -> None:
    """Recarrega `{chave: arranjo}` do que ela mandou calar."""
    global _DISPENSADAS
    with contextlib.suppress(Exception):
        _DISPENSADAS = {
            str(k): str(v.arranjo or "")
            for k, v in (declaracao.mesa.ordens_dispensadas or {}).items()}


def _reler_a_declaracao() -> Any:
    """O disco de novo, depois de um gesto que escreveu nele.

    O daemon grava sob lock e só então responde `{"ok": true}`
    (`_handle_machine_declare`), então quando a ponte volta o arquivo já mudou —
    reler aqui é o que faz a tela mostrar, no tique seguinte, o que ela acabou
    de escolher, em vez de continuar mostrando o padrão do desenho.
    """
    return _declaracao(recarregar=True)


def _conferencias() -> list[Any]:
    """As conferências que cabem NO TIQUE — as três que não forkam processo.

    ELAS TOCAM O SISTEMA (sysfs), logo podem demorar ou falhar — e uma falha
    aqui NÃO pode derrubar a aba. A lista vazia é um estado legítimo ("nada a
    apontar"); a exceção vira lista vazia com o motivo ao lado, para que a tela
    não confunda "examinei e está tudo bem" com "não consegui examinar" — que é
    o defeito que esta casa chama de *ausência de notícia lida como sucesso*.

    AS OUTRAS DUAS CONFERÊNCIAS E AS ORDENS NÃO ESTÃO AQUI, e a razão é a do
    bloco de leitura acima: `pareamentos` forka `busctl`. Elas chegam pelo
    **Examinar Portas**, em `_EXTRAS`.
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
                if it is not None:
                    itens.append(it)
        return itens
    except Exception:
        return []


def _itens_da_tela() -> list[Any]:
    """As linhas do Check-up: as três do tique mais o que o exame completo trouxe.

    O QUE ELA DISPENSOU NÃO VOLTA, e é a metade do gesto `ignorar` que o disco
    sozinho não entrega: `ordens_da_mesa.ordens_novas` compara o arranjo
    guardado com o de AGORA, e é essa comparação que faz a dispensa valer para o
    fato e não para a palavra. Sem este filtro, o ⊘ gravaria a decisão dela e a
    linha reapareceria no tique seguinte — *"botão que grava e não cala"*, que
    foi exatamente a razão medida em 01/09 para não ligar o ⊘ ainda.
    """
    conferidas = _conferencias()
    vistas = {getattr(i, "chave", "") for i in conferidas}
    for item in _EXTRAS:
        if getattr(item, "chave", "") in vistas:
            continue
        ordem = getattr(item, "ordem", None)
        if ordem is not None and _DISPENSADAS.get(ordem.chave) == ordem.arranjo:
            continue
        conferidas.append(item)
    return conferidas


#: O QUE SOBRA QUANDO O ESTADO NÃO ESTÁ NO MAPA — a mesma reserva que
#: `gui.aba_conexoes.html_do_exame` usa na sua linha (`("info", "NOTA")`).
#: "NOTA" é a palavra que não afirma: um estado que esta tela não conhece não
#: pode virar nem um verde nem um alarme.
_SELO_DESCONHECIDO = ("info", "NOTA")

#: UM ENDEREÇO DE PINTURA POR ESTADO, e é o que a `aba08.exame` prometia por
#: escrito desde 02/09/2026: *"as três classes do desenho (`ok`/`warn`/`info`)
#: continuam CRAVADAS por posição … ele pede um endereço por estado, não um"*.
#:
#: O DEFEITO QUE ISTO FECHA, fotografado na mesa dela em 03/09: o exame devolveu
#: TRÊS achados, os três `certo`, e a segunda linha mostrava a palavra **CERTO**
#: dentro da pílula **laranja** — porque a cor vinha da posição no desenho, não
#: do achado. A palavra era do produto; a cor, do mockup.
#:
#: POR QUE UM ENDEREÇO POR ESTADO E NÃO UM SÓ: o alvo `classe` do
#: `hefesto_vivo.BOOTSTRAP` acende UMA classe por elemento
#: (`data-hef-classe`/`data-hef-quando`), e o vocabulário de endereço é UM
#: `data-campo` por nó. Um elemento só não tem como escolher entre quatro
#: cores — precisa de um interruptor por estado. O desenho os põe como três
#: `<i class="est">` invisíveis antes da pílula, e a folha de estilo os lê pelo
#: irmão (`.est-ok.on ~ .selo`). O quarto continua sendo a própria pílula, que
#: já tinha `data-campo="selo-estado"`.
#:
#: `problema` FICA NA PÍLULA de propósito: é o único estado cuja cor é um
#: ACRÉSCIMO (`.selo.grave`, o vermelho de 02/09) e não uma substituição, e
#: mudá-lo de endereço quebraria a única metade que já funcionava.
ENDERECO_DO_ESTADO = {
    "certo": "selo-certo",
    "atencao": "selo-atencao",  # (noqa-acento) chave de máquina, ASCII por contrato
    "problema": "selo-estado",
    "nao_sei": "selo-nao-sei",
}


def _selos_por_estado(itens: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Uma lista por estado, e cada uma só responde à SUA pergunta.

    CADA ELEMENTO PERGUNTA UMA COISA SÓ. Um nó com
    ``data-hef-quando="problema"`` pergunta *"o estado desta linha é
    `problema`?"*, e as respostas possíveis são `problema` e o vazio — nunca
    `certo`, que é a resposta de OUTRA pergunta.

    ERA ISSO QUE ESTAVA ERRADO até 03/09/2026: o pacote emitia o estado CRU no
    único endereço que havia, e com os três achados `certo` da mesa dela a régua
    do mockup acusava três ENDEREÇOS MORTOS — *"o pacote declara 'certo' e a
    tela continua em ''"*. A tela estava certa (a linha não é `problema`, logo o
    vermelho não acende); quem falava a língua errada era o pacote.

    O VAZIO NÃO É "NÃO SEI": é o `não` desta pergunta. O `escrever()` do piloto
    o traduz em travessão e o alvo `classe` trata travessão como apagado
    (`hefesto_vivo.BOOTSTRAP`, a função `ligado`), que é exatamente o que se
    quer — apagar a cor daquele estado.
    """
    return {
        endereco: [
            (i["estado"] if i["estado"] == estado else "") for i in itens
        ]
        for estado, endereco in ENDERECO_DO_ESTADO.items()
    }


def _selo_do_estado(estado: str) -> tuple[str, str]:
    """``(a classe CSS, a palavra)`` do selo — do dono, `gui.aba_conexoes`.

    O MAPA TEM UM DONO e ele já traduzia os quatro estados do `exame_da_mesa`
    para as três palavras que o desenho dela crava. Ele mora na camada de tela
    porque é vocabulário, e não máquina — o próprio módulo do exame diz que
    "responde por máquina, não por vocabulário".

    O IMPORT É TARDIO pela razão de sempre neste arquivo: `gui.aba_conexoes`
    puxa a cadeia de tela, e o topo deste módulo tem de continuar importável
    numa árvore sem `src/` no caminho.

    A PALAVRA DE `problema` AINDA É A DE `atencao` — 02/09/2026, e é  (noqa-acento)
    ESPERA DELA. O mapa do dono manda os dois estados para **AJUSTAR**, e ela
    decidiu que *"o que está quebrado agora não pode parecer igual ao que só
    podia estar melhor"*. **A COR já saiu** (ver `selo-estado`, na
    :func:`pacote`, e a regra `.selo.grave` do gerador); a PALAVRA é dela, e
    trocá-la aqui seria escolher no lugar dela. Quando ela disser, quem muda é
    `gui.aba_conexoes.SELO_DO_ESTADO` — e ali a mudança alcança a janela GTK
    junto, porque a linha dela lê o mesmo mapa (`html_do_exame`).
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui.aba_conexoes import SELO_DO_ESTADO

    return SELO_DO_ESTADO.get(estado, _SELO_DESCONHECIDO)


def _dica_da_linha(item: Any) -> str:
    """O `?` de uma linha do Check-up, em HTML: o que importa e a cura.

    DUAS METADES, E NÃO TRÊS — decisão dela, 02/09/2026: *"o ponto de
    interrogação para de repetir a linha"*. Com a publicação de hoje a linha
    passou a mostrar a MEDIÇÃO (`Item.porque`, ver a chave `achado` do
    :func:`pacote`), e a dica ao lado repetia a mesma frase na segunda metade.
    O que sobra é o que a linha NÃO diz: **por que aquilo importa**
    (`DICAS_DAS_LINHAS`, por chave de regra) e **o que fazer**
    (`PREFIXO_DA_CURA` + `Item.cura`).

    AS DUAS FRASES CONTINUAM SENDO DO PRODUTO. O que esta função monta é a
    ORDEM entre elas; nenhuma palavra é escrita aqui, e as duas constantes são
    as mesmas que `secao_exame._dica_do_item` usa. Uma frase reescrita aqui
    seria a quarta grafia da mesma dica.

    POR QUE O PACOTE PEDE A METADE, E NÃO O DONO MUDA — a alternativa foi
    medida e recusada. `_dica_do_item` é do GTK também
    (`secao_exame.PainelDoExame`, `:1181`), e ali a linha mostra
    `item.rotulo` — o NOME da conferência (`:1177`). Naquela janela a dica é o
    ÚNICO caminho de `Item.porque` até a tela; cortar a metade do meio no dono
    apagaria a medição da janela estável para curar uma repetição que só existe
    AQUI. Duas telas mostram coisas diferentes na linha, logo elas pedem
    dicas diferentes — e quem pede é quem sabe o que já mostrou.

    SÓ A QUEBRA DE LINHA É NOSSA. O dono junta com `\\n\\n` porque escreve num
    `set_tooltip_text` do GTK; esta tela é HTML, onde `\\n` não quebra nada — o
    `?` sairia com as frases coladas. `<br><br>` é a tradução, e é o que o
    desenho dela já usa nas dicas cravadas.

    E O TEXTO É ESCAPADO ANTES: o alvo é `html`, então um `&` ou um `<` vindo do
    exame viraria marcação. O escapador é o da camada de tela desta aba
    (`gui.aba_conexoes._e`), o mesmo que o gerador do desenho usa.

    O `except` LARGO É DE PROPÓSITO E DEVOLVE VAZIO: com `""` o `escrever()`
    põe o travessão, que é "não tenho o que dizer aqui". A alternativa —
    deixar levantar — derrubaria a pintura da aba INTEIRA por causa de uma
    dica, e a alternativa silenciosa (não emitir a chave) deixaria a dica do
    MOCKUP na tela ao lado do achado dela, que é o defeito que este endereço
    nasceu para matar.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_exame import (
            DICAS_DAS_LINHAS,
            PREFIXO_DA_CURA,
        )
        from hefesto_dualsense4unix.gui.aba_conexoes import _e
        from hefesto_dualsense4unix.utils.i18n import _

        # O `_()` É O MESMO DO DONO (`secao_exame` importa este). Sem ele, as
        # duas dicas da mesma linha sairiam por caminhos de tradução
        # diferentes na hora em que esta casa tiver um segundo idioma.
        partes = [_(str(DICAS_DAS_LINHAS.get(str(getattr(item, "chave", "")), "")))]
        cura = str(getattr(item, "cura", "") or "")
        if cura:
            partes.append(_(PREFIXO_DA_CURA) + _(cura))
        return "<br><br>".join(_e(p) for p in partes if p)
    except Exception:
        return ""


def _carimbo_do_exame() -> str:
    """O "Examinado …" do topo do Check-up.

    A PALAVRA DA IDADE É DO PRODUTO — `secao_exame.frase_de_quando`, que já
    arredonda grosso de propósito ("Há 3 minutos", e não "Há 187 segundos"). A
    moldura *"Examinado …"* é deste desenho, e é por isso que ela fica aqui e
    não lá.

    ANTES DO PRIMEIRO **Examinar Portas** A RESPOSTA É "agora mesmo", e ela é
    verdadeira: as três conferências que a tira mostra são refeitas a cada
    tique (`_conferencias`), logo o que está na tela foi medido neste segundo.
    O que envelhece é o exame COMPLETO — as cinco conferências e as ordens de
    serviço —, e esse tem hora marcada pelo botão.

    O CARIMBO NÃO SABIA NADA ATÉ HOJE: o `<span class="conta">` do desenho
    dizia "Examinado há 3 minutos" desde que o mockup nasceu, sem endereço e
    sem dono. Uma frase de tempo que nunca muda é a forma mais barata de a tela
    afirmar o que não mediu.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_exame import frase_de_quando

    idade = 0.0 if _QUANDO_O_EXAME is None else max(0.0, time.monotonic() - _QUANDO_O_EXAME)
    return f"Examinado {frase_de_quando(idade).lower()}"


def _linha(item: Any) -> dict[str, Any]:
    """Um `Item` do exame na forma que a tela consome.

    OS CAMPOS SÃO `rotulo`, `estado` e `porque` — os do `exame_da_mesa.Item`,
    lidos do dataclass. A primeira versão daqui pedia `titulo` com `or str(it)`
    de reserva, e o `Item` não tem `titulo`: a reserva ganhava sempre e o
    **`repr` do objeto Python foi parar na tela dela**, visível na foto de
    01/09 — `Item(chave='energia_do_radio', rotulo='Economia de energia
    desligada', estado='a`, cortado no meio.

    Um `getattr` com reserva é o disfarce perfeito para um campo que não existe:
    ele não levanta, e o que sai parece dado.

    A PALAVRA DO SELO E A DICA SÃO DO PRODUTO — 02/09/2026. Antes, o pacote
    montava as duas à mão, e as duas erravam:

    * o selo saía de um `"AJUSTAR" if grave else "CERTO"`, e o `Item` tem
      QUATRO estados. `gui.aba_conexoes.SELO_DO_ESTADO` os mapeia em TRÊS
      palavras, e a que sumia era a **NOTA** do `nao_sei` — a mesma que o
      desenho dela crava na quarta linha do Check-up. Um "não deu para olhar"
      chegava à tela como "AJUSTAR", que é a tela afirmando um problema que
      ninguém mediu;
    * o `?` da linha não era montado de jeito nenhum — ver o `dica` abaixo.
    """
    estado = str(getattr(item, "estado", "") or "")
    ordem = getattr(item, "ordem", None)
    return {
        "chave": str(getattr(item, "chave", "")),
        "titulo": str(getattr(item, "rotulo", "") or ""),
        "porque": str(getattr(item, "porque", "") or ""),
        "estado": estado,
        # A PALAVRA E A CLASSE, do dono.
        #
        # FATO ERRADO, SUBSTITUÍDO em 02/09/2026: estas linhas diziam que a
        # classe *"ainda NÃO é pintada: o `escrever()` do piloto conhece cinco
        # alvos (`texto`, `largura`, `fundo`, `valor`, `html`) e nenhum acende
        # ou apaga uma classe CSS"*. Ele conhece SETE, e dois deles nasceram
        # para exatamente isto: `classe` (`hefesto_vivo.py:217`, com
        # `data-hef-classe` e `data-hef-quando`) e `cor` (`:246`). O que a
        # linha descrevia — CERTO dentro da pílula laranja do desenho —
        # continua verdadeiro e continua sendo defeito; o que não é mais
        # verdade é que falte caminho.
        #
        # A CLASSE DAQUI SEGUE SENDO INFORMATIVA, e de propósito: quem acende a
        # pílula é o `selo-estado` da :func:`pacote`, que emite o ESTADO cru e
        # deixa a gramática de cor no desenho (`aba08.exame`). Emitir a classe
        # como valor de pintura poria a folha de estilo dentro do Python.
        "selo": _selo_do_estado(estado)[1],
        "classe": _selo_do_estado(estado)[0],
        "dica": _dica_da_linha(item),
        # `certo` é o único estado que não pede nada — os outros
        # (`ajustar`, `atencao`) são achados de verdade.  # (noqa-acento) id
        "grave": estado.lower() not in {"certo", ""},
        # A ORDEM VAI COMO DUAS STRINGS, e não como o objeto: este dicionário
        # atravessa o `normalizar` e vira JSON para o WebView. O objeto vivo
        # fica em `_ORDENS_NA_TELA`, que é quem o `ignorar` consulta.
        "ordem": "" if ordem is None else str(ordem.chave),
        "arranjo": "" if ordem is None else str(ordem.arranjo),
    }


def _exame() -> list[dict[str, Any]]:
    """As linhas do Check-up, em dicionário. **ESTE NOME É CONTRATO.**

    A ABA JOGAR CHAMA ISTO (`a01_jogar._do_exame`), e é de propósito: o aviso do
    cartão dela sai do MESMO exame desta aba — *"duas contagens do mesmo fato
    divergiriam no primeiro achado novo"*, diz o comentário de lá. Uma aba
    consome a outra, e o nome é a fronteira entre as duas.

    MEDIDO EM 01/09/2026, E QUASE PASSOU: esta função tinha sido dividida em
    `_conferencias()` + `_itens_da_tela()` e o nome `_exame` sumiu. O `_do_exame`
    da Jogar embrulha a chamada num `except Exception: return []`, então o
    `AttributeError` virou **lista vazia** — e a aba Jogar parou de emitir
    `aviso-selo` e `aviso-texto` sem uma linha de erro em lugar nenhum. Quem
    acusou foi o `test_o_casamento_das_dez`, dizendo que a Jogar casava 7
    endereços e o piso era 9.

    É a armadilha desta casa em duas camadas: um `except Exception` largo comeu
    o erro, e o sintoma foi a AUSÊNCIA de dado — que se lê como "não havia
    achado nenhum". Renomear uma função privada de um pacote pode apagar meia
    tela de outro.
    """
    return [_linha(i) for i in _itens_da_tela()]


def _adaptadores(conectados: Any) -> dict[str, Any]:
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


def _bancada() -> Any:
    """A mesa do motor montada sobre o rascunho DELA — ou `None` sem censo.

    `None` não é borda: sem censo o motor não tem o que julgar, e o mapa sai
    com as entradas e sem veredito. É honesto — um veredito inventado sobre um
    barramento que ninguém leu seria pior que a ausência dele.
    """
    censo = _censo()
    if censo is None:
        return None
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import bancada_do_rascunho

    with contextlib.suppress(Exception):
        return bancada_do_rascunho(_logica_do_mapa(), censo)
    return None


def _html_do_mapa() -> str:
    """As faces do gabinete DELA, desenhadas pelo produto.

    O DESENHO É UM SÓ (`gui/aba_conexoes.html_do_mapa`) e o gerador do mockup
    usa o MESMO — a diferença é o dado: lá é a cena de bancada, aqui é o que ela
    declarou. Foi assim que a extração se provou fiel: a página regerada saiu
    byte a byte igual à que ela aprovou.

    O VEREDITO VEM DO MOTOR, e não de uma cópia: `veredito_do_quadrado` chama
    `arranjo_da_mesa.julgar`, que sabe de entrada azul, de folga na fileira e de
    extensor — e CONFESSA o que não sabe. O gerador tinha uma reescrita à mão
    disso, com os cinco vereditos digitados.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.widgets import mapa_da_mesa as mm
    from hefesto_dualsense4unix.gui import aba_conexoes as _tela

    logica = _logica_do_mapa()
    bancada = _bancada()

    def veredito_de(numero: str, esticada: bool) -> tuple[str, str, str]:
        if bancada is None:
            return "", "", ""
        v = mm.veredito_do_quadrado(bancada, numero, logica.escolhido)
        return ("", "", "") if v is None else (v.v, v.texto, v.porque)

    quem_esta: dict[str, tuple[str, str]] = {}
    censo = _censo()
    por_caminho = {a.nome_do_kernel: a for a in (censo.conectados() if censo else ())}
    for numero, porta in logica.portas.items():
        caminho = str(porta.get("caminho") or "")
        if not caminho:
            continue
        achado = por_caminho.get(caminho)
        quem_esta[numero] = (achado.especie if achado else caminho, caminho)

    extensoes = {str(p.get("filha_de")): n
                 for n, p in logica.portas.items() if p.get("filha_de")}

    return _tela.html_do_mapa(
        [{"nome": f["nome"], "portas": f["portas"]} for f in logica.faces],
        quem_esta=quem_esta,
        extensoes=extensoes,
        veredito_de=veredito_de,
        rotulos={"vazia": mm.ROTULO_VAZIA,
                 "por_extensao": mm.ROTULO_POR_EXTENSAO,
                 "nova_entrada": mm.ROTULO_NOVA_ENTRADA},
        dicas={"esticada": mm.DICA_EXTENSAO, "enumera": mm.DICA_ENUMERA,
               "nova_entrada": _tela.DICA_NOVA_ENTRADA,
               "novo_hub": _tela.DICA_NOVO_HUB})


def _html_dos_aparelhos() -> str:
    """O que o censo achou — o PRIMEIRO tempo do gesto de dois tempos.

    A lista era a constante `CENSO` do gerador: sete aparelhos de exemplo. Aqui
    são os do barramento DELA, e é o que faz `escolher-aparelho` deixar de ser
    um botão que escolhe um aparelho que não existe.

    O `data-caminho` É O ENDEREÇO, e ele é o `nome_do_kernel`: o rótulo repete
    entre dois adaptadores iguais (`rotulo_do_aparelho` diz por quê), e clicar
    por rótulo escolheria o errado.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.widgets import mapa_da_mesa as mm
    from hefesto_dualsense4unix.gui.aba_conexoes import _e

    censo = _censo()
    if censo is None:
        return ""
    logica = _logica_do_mapa()
    onde_esta = {str(p.get("caminho")): n for n, p in logica.portas.items()
                 if p.get("caminho")}
    fora = []
    for a in mm.aparelhos_para_colocar(censo):
        caminho = a.nome_do_kernel
        em = onde_esta.get(caminho, "")
        dica = (mm.DICA_JA_COLOCADO.format(n=em) if em else "")
        aceso = " on" if logica.escolhido == caminho else ""
        fora.append(
            f'          <button class="mm-ap{aceso}" data-gesto="escolher-aparelho" '
            f'data-caminho="{_e(caminho)}" title="{_e(dica)}">{_e(a.especie)}'
            f'<span class="pt">·</span><code>{_e(caminho)}</code></button>')
    return "\n".join(fora)


# ---------------------------------------------------------------------------
# A IDENTIDADE DO CONTROLE — `IDENTIDADE-VEM-DE-CIMA-01`, 03/09/2026
#
# A LEI É DELA: *"se no topo tá mostrando controle white player 1, então cada
# aba vai usar os controles lá de cima. Não mistura com a info dos mockups."*
#
# AS TRÊS FUNÇÕES ABAIXO TÊM DOIS CHAMADORES E UM DONO, e é o molde que a
# `a04_iluminacao.um_botao_de_player` já provou: o gerador `aba08.py` as chama
# com a mesa da BANCADA para desenhar o mockup, e este pacote as chama a cada
# tique com a mesa VIVA. Enquanto eram duas escritas — uma no gerador, outra
# nenhuma —, o desenho mandava na tela do produto: com o White dela no cabo, a
# Gestão de Controles continuava dizendo `Cosmic Red`.
# ---------------------------------------------------------------------------
#: O que a mesa põe no lugar do nome do plástico quando ninguém leu a cor.
#: `mesa_viva.COR_DESCONHECIDA` é o dono; repetir a string aqui criaria uma
#: segunda cópia que envelhece sozinha.
def _cor_desconhecida() -> str:
    from hefesto_dualsense4unix.interface import mesa_viva

    return mesa_viva.COR_DESCONHECIDA


def rotulo_do_controle(c: Any, completo: bool = True) -> str:
    """A ordem dela, 26/08: marca • player • plástico • transporte.

    O PLÁSTICO SOME QUANDO NINGUÉM O LEU, e é a regra dela — *campo sem
    informação não mostra nada*. Pelo rádio o Hefesto ainda não pergunta a cor
    (`ONDA-CONEXOES-11`), e ali a mesa devolve `COR_DESCONHECIDA`: escrever
    "Não sei" no meio do rótulo seria uma palavra a mais para ler e nenhuma
    informação a mais; escrever a cor do desenho seria a mentira que esta
    sprint existe para matar.
    """
    marca = 'Sony <span class="pt">•</span> ' if completo else ""
    jogador = f'Player {c["jogador"]}' if completo else f'P{c["jogador"]}'
    nome = str(c.get("nome") or "")
    plastico = (f'{nome} <span class="pt">•</span> '
                if nome and nome != _cor_desconhecida() else "")
    return f'{marca}{jogador} <span class="pt">•</span> {plastico}{c["via"]}'


#: `--fg` e `--app-bg` do esqueleto. São cor de TEMA, não de plástico: o número
#: dentro do bloco precisa ser lido sobre qualquer um dos 28 modelos, e nenhum
#: dos dois candidatos serve para todos — `--fg` some no Starlight Blue,
#: `--app-bg` some no Galactic Purple.
_TINTAS_DE_TEXTO = (("var(--fg)", (0xF8, 0xF8, 0xF2)),
                    ("var(--app-bg)", (0x21, 0x22, 0x2C)))


def tinta_legivel(fundo_hex: str) -> str:
    """A tinta de texto que se lê sobre aquele plástico, pela conta da casa."""
    from hefesto_dualsense4unix.utils.color_contrast import razao_contraste

    rgb = tuple(int(fundo_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return max(_TINTAS_DE_TEXTO, key=lambda t: razao_contraste(rgb, t[1]))[0]


def _hex_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, ou `""` quando ninguém leu a cor.

    `monta.cor_da_zona` é o dono — ele LÊ a folha que pinta o desenho
    (`scripts/gerar_cores_do_dualsense.py`) em vez de digitar o hex.

    O `""` NÃO é desistência: a cor chega pelo broker, uma vez por endereço e em
    thread, então o primeiro tique de uma sessão sempre tem a mesa sem cor — e
    pelo RÁDIO o Hefesto ainda não pergunta (`ONDA-CONEXOES-11`). Sem hex, quem
    chama mostra a neutra. Inventar aqui seria a mentira que esta sprint mata.
    """
    if not slug:
        return ""
    try:
        import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

        return str(monta.cor_da_zona(slug))
    except Exception:
        # `cor_da_zona` levanta `SystemExit` para colorway que o SVG não tem.
        # Derrubar a pintura da aba por causa de um modelo novo seria trocar uma
        # barra que falta por uma tela congelada.
        return ""


# O DESENHO PEQUENO DA LINHA CONTINUA NO PLÁSTICO DO MOCKUP, e a razão está
# MEDIDA no CSS do `.ds-mini` em `aba08.py`: a cor dele mora num ATRIBUTO
# (`data-colorway`), o `escrever()` do piloto não tem alvo de atributo, e trocar
# o `<svg>` inteiro pelo alvo `html` custou 31 pinturas em 31 tiques e triplicou
# o tique (4,24 → 13,56 ms). A cura certa é um alvo de ATRIBUTO no piloto, que é
# arquivo de outro dono — e ela vale para as cinco abas que desenham controle.


def _da_mesa_para_a_regua(m: dict[str, Any], com_mic: set[str]) -> dict[str, Any]:
    """Um controle da mesa VIVA na língua da régua do rádio.

    O `"Não sei"` DA MESA VIRA VAZIO AQUI, e foi um vazamento medido em
    03/09/2026 com os dois controles dela: o `title` da fatia do rádio saía
    *"Não sei — 260,4 turnos de entrada"*. `COR_DESCONHECIDA` é o que a mesa
    responde quando ninguém leu a cor, e ele é para o Python decidir — não para
    a tela mostrar. Vazio faz quem lê cair no `Player N`, que é um fato.
    """
    nome = str(m.get("nome") or "")
    return {
        "jogador": m.get("jogador"),
        "nome": "" if nome == _cor_desconhecida() else nome,
        "via": str(m.get("via") or ""),
        "plastico": _hex_do_plastico(str(m.get("cor") or "")),
        # A PONTE QUE SUBIU, e não a que se pediu. É a mesma fonte que o
        # `radio_da_mesa.ocupacao_por_adaptador` usa (`bt_mic.uniqs`), com a
        # razão escrita lá: *"uma ponte pedida que não subiu não ocupa fatia de
        # rádio nenhuma"*. O desenho mostra a fatia laranja porque na bancada a
        # ponte está de pé; aqui ela só aparece quando está mesmo.
        "mic": (norm_mac(str(m.get("uniq") or "")) or "") in com_mic,
    }


def _regua_do_radio(ctx: Contexto) -> str:
    """A régua de Desempenho com a mesa DELA — pistas, eixo e legenda.

    O QUE O PRODUTO SABE, e é só isto: quem está no rádio (a mesa), em qual
    adaptador cada um está (`radio_da_mesa.adaptador_por_uniq`, que lê o
    `HID_PHYS` do sysfs) e quanto cada fatia custa (`radio_da_mesa`, os mesmos
    quatro números que o desenho já lia).

    O QUE ELE NÃO SABE É O NOME DO ADAPTADOR. O apelido mora na declaração dela,
    endereçado por CAMINHO de barramento, e aqui a chave é o endereço de rádio —
    as duas não casam hoje. Então a coluna diz **Sem nome**, que é a palavra que
    o próprio produto usa quando não há apelido
    (`gui/aba_conexoes.html_das_pistas`), e a dica fica VAZIA em vez de repetir
    o "TP-Link UB500 — Entrada 3" do desenho. Nenhuma palavra nova nasce aqui.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

    com_mic = {c for c in (norm_mac(str(u)) for u in
                           ((ctx.state.get("bt_mic") or {}).get("uniqs") or [])) if c}
    todos = [_da_mesa_para_a_regua(m, com_mic) for m in ctx.mesa]
    no_radio = [c for c in todos if c["via"] == "BT"]
    no_cabo = [c for c in todos if c["via"] != "BT"]

    onde: dict[str, str] = {}
    if no_radio:
        with contextlib.suppress(Exception):
            onde = rm.adaptador_por_uniq(
                [str(m.get("uniq") or "") for m in ctx.mesa if m.get("via") == "BT"])

    # UM GRUPO POR ADAPTADOR, e o SEM_ADAPTADOR por último. `adaptador_por_uniq`
    # devolve `""` para quem o sysfs não soube dizer, e a regra de honestidade é
    # dele: *"nunca empresta o adaptador do vizinho"*. Aqui isso vira uma pista
    # à parte, sem nome — e não uma fatia enfiada na pista de outro.
    grupos: dict[str, list[dict[str, Any]]] = {}
    for m, c in zip(ctx.mesa, todos, strict=True):
        if c["via"] != "BT":
            continue
        grupos.setdefault(onde.get(str(m.get("uniq") or ""), ""), []).append(c)

    pistas = [
        {"nome": "Sem nome", "dica": "", "dentro": grupos[chave], "vagas": no_cabo}
        for chave in sorted(grupos, key=lambda k: (k == "", k))
    ]
    return html_da_regua_do_radio(
        pistas, no_radio,
        teto=rm.SLOTS_POR_SEGUNDO,
        sem_mic=rm.HZ_INPUT_SEM_MIC * rm.SLOTS_POR_RELATORIO,
        com_mic=(rm.HZ_INPUT_COM_MIC + rm.HZ_AUDIO_COM_MIC) * rm.SLOTS_POR_RELATORIO,
        num=_num_da_tela, palavra=rm.palavra_da_ocupacao)


def _num_da_tela(valor: float) -> str:
    """`1600` → `1.600`; `260.4` → `260,4`. A vírgula tem dono único."""
    from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br

    inteiro, _, decimal = formata_pt_br(valor).partition(",")
    milhar = f"{int(inteiro):,}".replace(",", ".")
    return milhar if decimal == "0" and float(valor).is_integer() else f"{milhar},{decimal}"


def html_da_regua_do_radio(
    pistas: list[dict[str, Any]],
    no_radio: list[dict[str, Any]],
    *,
    teto: float,
    sem_mic: float,
    com_mic: float,
    num: Any,
    palavra: Any,
) -> str:
    """A régua de Desempenho inteira: as pistas, o eixo e a legenda.

    ELA SE TROCA INTEIRA e não campo a campo, pela razão que o piloto já
    escreve sobre a fita: *"um bloco cujo NÚMERO DE FILHOS muda com o dado não
    tem como ser pintado campo a campo — não há endereço para um filho que
    ainda não existe"*. Quantos adaptadores, quantos controles em cada um e
    quantas vagas mudam com a mesa dela.

    E ELA NÃO PODIA FICAR NO GERADOR: o `title` de cada bloco nomeia o plástico
    (*"Starlight Blue — 260,4 turnos de entrada"*), e `title` é texto que a tela
    mostra. Não há alvo de atributo no `escrever()` do piloto — a única forma
    honesta de curar um `title` congelado é o bloco inteiro nascer do produto.

    :param pistas: uma por adaptador — ``nome``, ``dica`` (o `title` da coluna
        da esquerda, vazio quando ninguém sabe), ``dentro`` e ``vagas``.
    :param no_radio: os controles no rádio, para a legenda.
    :param num: o formatador de número da tela (a vírgula tem dono único).
    :param palavra: a palavra da ocupação, do `radio_da_mesa`.
    """
    linhas = []
    for p in pistas:
        dica = f' title="{p["dica"]}"' if p.get("dica") else ""
        dentro = list(p.get("dentro") or [])
        if not dentro:
            linhas.append(
                f'        <div class="pista">\n'
                f'          <span class="quem"{dica}>{p["nome"]}</span>\n'
                f'          <span class="trilho"><span class="vazio">Nenhum controle '
                f'neste rádio</span></span>\n'
                f'          <span class="num">0 <i>de {num(teto)}</i></span>\n'
                f'        </div>')
            continue
        blocos, usado = [], 0.0
        for c in dentro:
            # SEM COR LIDA A FATIA FICA NEUTRA, e o texto volta para a tinta de
            # tema: pintar o bloco com a cor do desenho seria a mesma mentira,
            # um andar abaixo.
            plastico = str(c.get("plastico") or "")
            pinta = (f";background:{plastico};color:{tinta_legivel(plastico)}"
                     if plastico else "")
            nome = str(c.get("nome") or "") or f'Player {c["jogador"]}'
            blocos.append(
                f'<span class="bloco usa" style="width:{sem_mic / teto * 100:.2f}%{pinta}"'
                f' title="{nome} — {num(sem_mic)} turnos de entrada">'
                f'P{c["jogador"]} · {num(sem_mic)}</span>')
            usado += sem_mic
            if c.get("mic"):
                blocos.append(
                    f'<span class="bloco mic" style="width:{(com_mic - sem_mic) / teto * 100:.2f}%"'
                    f' title="Microfone do Player {c["jogador"]} pelo rádio — '
                    f'+{num(com_mic - sem_mic)} turnos"></span>')
                usado += com_mic - sem_mic
        for c in list(p.get("vagas") or []):
            if usado + com_mic > teto:
                break
            usado += com_mic
            quem = str(c.get("nome") or "") or f'Player {c["jogador"]}'
            blocos.append(
                f'<span class="bloco vaga" style="width:{com_mic / teto * 100:.2f}%"'
                f' title="Se o {quem} do Player {c["jogador"]} — hoje no {c["via"]} — viesse '
                f'para este rádio com o microfone ligado: +{num(com_mic)} turnos.">'
                f'+1 · {num(usado)}</span>')
        total = sum(com_mic if c.get("mic") else sem_mic for c in dentro)
        fracao = total / teto
        linhas.append(
            f'        <div class="pista">\n'
            f'          <span class="quem"{dica}>{p["nome"]}</span>\n'
            f'          <span class="trilho" title="{palavra(fracao)} — {num(total)} das '
            f'{num(teto)} turnos ({fracao * 100:.0f}%). As três palavras são do produto '
            f'(integrations/radio_da_mesa.py) e falam só de OCUPAÇÃO: rádio cheio tem volta, '
            f'basta tirar um controle daqui.">\n'
            f'            {"".join(blocos)}\n'
            f'          </span>\n'
            f'          <span class="num">{num(total)} <i>de {num(teto)}</i></span>\n'
            f'        </div>')
    legenda = [
        f'            <span><i style="background:{c["plastico"]}"></i>'
        f'{rotulo_do_controle(c, completo=False)} — {num(sem_mic)}</span>'
        for c in no_radio if c.get("plastico")
    ]
    return (
        "\n".join(linhas) + "\n"
        '          <div class="eixo">\n'
        '            <span class="quem"></span>\n'
        '            <span class="regua"><i>0</i><span>400</span><span>800</span>'
        f'<span>1.200</span><span>{num(teto)}</span></span>\n'
        '            <span class="num"></span>\n'
        '          </div>\n'
        '\n'
        '          <div class="leg">\n'
        + ("\n".join(legenda) + "\n" if legenda else "")
        + f'            <span><i style="background:var(--orange)"></i>O microfone de cada um '
          f'— +{num(com_mic - sem_mic)}</span>\n'
          f'            <span><i class="vaga"></i>Cada controle do cabo, se viesse '
          f'— +{num(com_mic)}</span>\n'
          '          </div>')


# ---------------------------------------------------------------------------
# O TETO DA VIBRAÇÃO POR CONTROLE — MIGRA-CONEXOES-11, 01/09/2026
# ---------------------------------------------------------------------------
# A CADEIA JÁ EXISTIA INTEIRA, e nada dela é desta leva. O que faltava era a
# tela escrever no perfil:
#
#   perfil `controllers[chave].rumble.policy`   o que esta feature grava
#     → `profiles/manager._controllers_to_rumble_scales:1834`  vira fator
#       RELATIVO (mult da peça / mult global), e o 1,0 é descartado
#     → `profiles/manager.ProfileManager.apply:459-464`          publica o mapa
#     → `core/backend_pydualsense.set_rumble_scales:3820`      guarda
#     → `core/backend_pydualsense._escalar_rumble:3797`        multiplica o
#       que vai ao motor, nas DUAS rotas de escrita (broadcast e por MAC)
#
# A CONTA, medida no disco dela em 01/09/2026: os 33 perfis têm
# `rumble.policy = None` e ZERO têm `controllers[*].rumble`. Sem opinião
# global, a base de `_controllers_to_rumble_scales` é o
# `_RUMBLE_POLICY_PADRAO = "balanceado"` (mult 1,0), então um override
# `economia` publica `0.3 / 1.0 = 0.3` — exatamente os "30% da força" que o
# rótulo promete, derivados do mesmo dono (`RUMBLE_POLICY_MULT["economia"]`).
#
# O QUE A RECUSA DIZIA ESTAVA ERRADO NAS DUAS METADES, e a regra desta casa
# manda substituir o fato errado, não anotá-lo. Ela dizia que *"o produto
# aplica `min` (`core/rumble.py`)"* e que *"sobrepor mudaria o daemon"*. O
# `min` de `core/rumble.py:108` compara a política GLOBAL com o teto do
# ORÇAMENTO — nenhum dos dois é por controle —, e o caminho por controle não
# passa por ali: ele é um FATOR aplicado um andar abaixo. Sobrepor não muda
# uma linha do daemon.


def _orcamento_da_mesa() -> tuple[str | None, bool]:
    """``(a chave do orçamento declarada, a mesa respondeu?)``.

    O SEGUNDO ITEM EXISTE PORQUE O SILÊNCIO VIRAVA AFIRMAÇÃO — 01/09/2026. Esta
    função devolvia só `str | None` com um `except Exception: return None` por
    baixo, e o `None` de "não consegui ler" era o MESMO de "ninguém declarou";
    a dica publicava os dois como a palavra em negrito **"Sem teto"**. O dono da
    fonte proíbe isso com todas as letras (`secao_orcamento.orcamento_em_vigor`:
    *"None aqui significa 'não sei', nunca 'sem teto'"*).

    LÊ DA DECLARAÇÃO QUE O MÓDULO JÁ TEM EM CACHE, e não do disco de novo. O
    `_declaracao()` (:100) guarda o `maquina.json` inteiro validado, e
    `MaquinaConfig.orcamento.teto` é exatamente o campo que
    `orcamento_em_vigor()` devolveria — `carregar_maquina().orcamento.teto`, o
    corpo dela. A leitura antiga abria o arquivo a cada tique E arrastava
    `gi`/GTK para o processo (por `app.widgets.segmented_selector`), para zero
    informação nova.
    """
    declaracao = _declaracao()
    if declaracao is None:
        return None, False
    return getattr(getattr(declaracao, "orcamento", None), "teto", None), True


def _teto_do_controle(
    overrides: dict[str, Any],
    uniq: str,
    vibracao: Vibracao,
    sem_dono: dict[str, str],
) -> tuple[str | None, str]:
    """``(o que o CAMPO mostra, a frase do ?)`` para UM controle.

    `vibracao` é a `gui.aba_conexoes.Vibracao` com o que vale para a mesa
    INTEIRA — o global do perfil, o global VIVO do daemon e o orçamento —, e
    esta função só lhe acrescenta o override desta peça. Os três eram um
    argumento `orcamento` só até 01/09/2026, e a tela reportava o errado: o `?`
    dizia *"o global vale Sem teto"* enquanto o daemon cortava a 0,3.

    A CHAVE É O `uniq` NORMALIZADO — doze hexa minúsculos sem separador, e a
    normalização é do :func:`_so_hex` deste arquivo, nunca escrita de novo. É o
    que `Profile._validate_controllers_keys` canoniza ao carregar
    (`profiles/schema.py:1205-1228`), logo é o que está no disco; procurar por
    `aa:bb:…` não acharia nada e a tela mostraria "Segue o global" para sempre.
    A cópia que morava aqui tinha perdido o `.strip()` do helper, e um `uniq`
    com espaço ou quebra fazia a gravação cair numa chave e a pintura procurar
    outra. O `uniq` cru continua sendo tentado como segunda chave porque
    `perfil.ativo` lê o JSON **sem** o pydantic (de propósito, para uma seção
    nova não congelar a aba inteira) — um arquivo editado à mão pode trazer a
    grafia com dois-pontos, que o loader só canoniza quando alguém o carrega.

    POLÍTICA QUE O CAMPO NÃO SABE MOSTRAR VIRA `sem_dono`, NÃO uma opção
    errada. O `<select>` mostra três coisas e `ControllerRumbleOverride` aceita
    quatro políticas; só o `economia` tem opção no campo
    (`gui.aba_conexoes.rotulo_da_politica` diz por quê). Um perfil escrito pela
    janela estável — `app/actions/rumble_actions.py:947` — ou editado à mão
    guarda uma das outras três. Medido em 01/09/2026: zero dos 33 perfis dela
    têm `controllers[*].rumble`, então o caso é hoje inalcançável — e é por isso
    mesmo que ele tem de estar escrito, e não descoberto pela próxima pessoa.
    """
    from hefesto_dualsense4unix.gui import aba_conexoes as _tela

    chave = _so_hex(uniq)
    dele = overrides.get(chave) or overrides.get(uniq) or {}
    seu = (dele.get("rumble") or {}) if isinstance(dele, dict) else {}
    policy = seu.get("policy") if isinstance(seu, dict) else None
    v = _dataclasses.replace(vibracao, do_controle=policy)
    campo, _ = _tela.teto_que_vale(v)
    # A FRASE INTEIRA, e não só a cláusula do meio. Medido em 01/09/2026, na
    # tela viva: pintar o `teto_que_vale(...)[1]` substituía a dica do desenho
    # por "este controle segue o global, que vale Sem teto" e APAGAVA o resto —
    # em que aba o global se muda e de onde vem o degrau. Pintar é trocar o
    # `innerHTML` inteiro, então o que não for pintado é perdido.
    frase = _tela.dica_do_teto(v)
    if campo is None:
        sem_dono[f"controle.{chave}.vibracao.teto"] = (
            f"o perfil guarda a política {policy!r} para este controle, e o "
            f"campo desta tela só sabe mostrar {list(_tela.opcoes_do_teto())}. "
            f"Escolher uma das três seria a tela afirmar um estado que o disco "
            f"contradiz — o `?` ao lado diz o que há, e a caixa fica parada.")
    return campo, frase


@registrar("08-conexoes.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    global _ORDENS_NA_TELA, _VIZINHOS
    st = ctx.state
    vivos = _itens_da_tela()
    itens = [_linha(i) for i in vivos]
    # A PONTE ENTRE O CLIQUE E A ORDEM, e ela se refaz a cada pintura: o ⊘ da
    # posição N age sobre o que foi PINTADO na posição N. Guardar a lista aqui,
    # e não montá-la no gesto, é o que garante que as duas concordem — se a
    # tira mudar entre a pintura e o clique, o clique age sobre o que ela
    # estava vendo, que é o único alvo defensável.
    _ORDENS_NA_TELA = tuple(getattr(i, "ordem", None) for i in vivos)
    # O QUE SOBRA NÃO É CLICÁVEL, E NÃO É MENTIRA: o desenho tem CINCO linhas de
    # exame e QUATRO blocos de vizinho. Se a mesa dela render mais — três ordens
    # de serviço abertas, sete rádios espetados —, a pintura escreve nos lugares
    # que existem e o resto não aparece. Nenhum clique age sobre o alvo errado
    # (o `data-v` só vai até 4 e o `_slot` confere a faixa), mas a tela ESCONDE.
    # É o mesmo buraco que `gui/aba_conexoes.sobraram` mede na janela estável, e
    # ali quem chama tem de dizê-lo. Aqui não há onde dizer ainda: nem o exame
    # nem os vizinhos têm um "+N" no desenho dela. Fica escrito para quem
    # desenhar o próximo.

    adap = _adaptadores(ctx.conectados)
    declaracao = _declaracao()

    # OS VIZINHOS SÃO OS DELA, e não os quatro do desenho. Enquanto eram os do
    # desenho, o `<select>` "— O que é? —" só podia gravar no `maquina.json`
    # dela um rádio da bancada de exemplo — a razão pela qual este gesto passou
    # a primeira leva sem dono.
    radios = tuple(getattr(_mesa_do_radio(), "radios", ()) or ())
    _VIZINHOS = tuple(_chave_do_radio(r) for r in radios)
    _, rotulo_do_tipo = _tipos_de_radio()
    pergunta = _a_pergunta()
    declarados = _radios_declarados(declaracao)
    vizinho_nome, vizinho_tipo = [], []
    for chave in _VIZINHOS:
        # `vid:pid` É O NOME QUE O PRODUTO TEM. A GUI estável escreve o mesmo
        # (`gui/aba_conexoes.html_dos_vizinhos`), e a tela já explica por quê:
        # *"o sistema entrega o nome cru e não sabe o que é"*. Um nome bonito
        # aqui seria adivinhação a partir do vid.
        vizinho_nome.append(chave)
        vizinho_tipo.append(rotulo_do_tipo.get(declarados.get(chave, ""), pergunta))

    # O TETO DA VIBRAÇÃO TEM TRÊS FONTES, E DUAS DELAS SE CHAMAVAM "O GLOBAL"
    # — corrigido em 01/09/2026, e foi o defeito que segurou esta leva:
    #
    #   perfil.rumble.policy   o DENOMINADOR do fator por peça
    #                          (`profiles/manager.py:1857`)
    #   state['rumble_policy'] o que MULTIPLICA no funil do motor
    #                          (`daemon/ipc_handlers.py:2864` → `_effective_mult`)
    #   maquina.json           o teto por CIMA da viva, com `min`
    #
    # As três são lidas UMA vez para as quatro linhas — ler dentro do laço
    # abriria os mesmos arquivos quatro vezes por tique. A viva vem do `state`
    # DESTE tique, que já a traz: era a cura na mão de quem pinta.
    perfil_ativo = perfil.ativo(st.get("active_profile"))
    overrides = (perfil_ativo.get("controllers") or {}) if perfil_ativo else {}
    global_do_perfil = ((perfil_ativo.get("rumble") or {}).get("policy")
                        if perfil_ativo else None)
    orcamento, mesa_respondeu = _orcamento_da_mesa()
    from hefesto_dualsense4unix.gui.aba_conexoes import Vibracao

    vibracao = Vibracao(
        do_perfil=global_do_perfil,
        a_viva=st.get("rumble_policy"),
        orcamento=orcamento,
        a_mesa_respondeu=mesa_respondeu,
    )
    sem_dono: dict[str, str] = {}

    # A MESA POR `uniq` — a identidade de cada controle, lida do aparelho. É de
    # onde saem o rótulo da linha e a cor da barra; o `ctx.conectados` traz o cru
    # do daemon e não sabe o nome do plástico.
    da_mesa = {str(m.get("uniq") or ""): m for m in ctx.mesa}

    colunas = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        teto_campo, teto_frase = _teto_do_controle(overrides, uniq, vibracao, sem_dono)
        eu = da_mesa.get(uniq) or {}
        colunas[uniq] = {
            "via": (c.get("transport") or "").upper(),
            "bateria": c.get("battery_pct"),
            # O NOME DA LINHA — `IDENTIDADE-VEM-DE-CIMA-01`, 03/09/2026. A
            # `.gc-nome` mostrava o rótulo do MOCKUP: com o White dela no cabo,
            # a Gestão de Controles dizia `Sony · Player 1 · Cosmic Red · USB`.
            # O alvo é `html` porque o rótulo traz os `<span class="pt">•</span>`
            # que separam os campos — em `texto` eles apareceriam escritos.
            "nome": rotulo_do_controle(eu) if eu else "",
            # A COR DA BARRA DA ESQUERDA, no alvo `cor` (ver o CSS do `.gc-cor`).
            # VAZIO APAGA, e é o alvo que garante: `el.style.color = ''` devolve
            # o elemento à folha de estilo, que o pinta `transparent`. Sem cor
            # lida — o rádio, enquanto a `ONDA-CONEXOES-11` não chegar — a barra
            # some e a borda neutra fica. Nenhuma cor é inventada.
            "plastico": _hex_do_plastico(str(eu.get("cor") or "")),
            "ponte": bool(c.get("uniq") in (st.get("pontes_confirmadas") or {})),
            "fragil": bool(c.get("uniq") in (st.get("native_bt_fragil_controles") or [])),
            # O QUE ESTÁ DECLARADO, e não o que o desenho traz. O `<select>`
            # nasce em "Ligado" no HTML; sem esta linha, desligar a ponte
            # gravava no disco e a tela continuava dizendo "Ligado" — e o
            # segundo clique dela pareceria o primeiro.
            "mic-existe": "Ligado" if _mic_declarado(declaracao, uniq) else "Desligado",
            # O `?` DO TETO VAI SEMPRE, e o campo só quando há o que escolher.
            # Pintar só a caixa deixaria a tela dizendo "30% da força" no campo
            # e "este controle segue o global" na dica — uma contradição NOVA,
            # nossa. O contrário (só a dica) é o caso declarado em `sem_dono`.
            "teto-explica": teto_frase,
        }
        if teto_campo is not None:
            colunas[uniq]["teto-da-vibracao"] = teto_campo
    return {
        "colunas": colunas,
        # O MAPA DO GABINETE, trocado INTEIRO — 01/09/2026. Ele não se pinta
        # campo a campo porque o número de faces e de entradas é o que ELA
        # declarou, e pode ser zero; não há endereço para um quadrado que ainda
        # não existe. É a mesma razão da fita.
        #
        # E ATÉ HOJE ELE NÃO SE PINTAVA DE JEITO NENHUM: o desenho era
        # `FACES`/`QUEM_ESTA`, constantes de bancada, e o `maquina.json` dela
        # nem existe. A aba mostrava um gabinete que não é o dela — e era por
        # isso que os seis botões do mapa não podiam ser ligados: clicar
        # declararia no disco DELA o desenho de um exemplo.
        # A `.mm-lista` SAIU DAQUI e virou campo com endereço — 03/09/2026. Ela
        # já era trocada inteira desde 01/09, mas por SELETOR, e um bloco sem
        # `data-campo` é invisível para as duas réguas: os `title` dos botões
        # nomeiam o plástico ("o P1 Cosmic Red, no cabo") e passavam por
        # congelados. A troca é a mesma — `data-hef-alvo="html"` também escreve
        # `innerHTML` —, e agora as réguas a enxergam.
        "blocos": {".mm-faces": _html_do_mapa()},
        "aparelhos": _html_dos_aparelhos(),
        # A RÉGUA DO RÁDIO INTEIRA, pelo dono único. Ver
        # `html_da_regua_do_radio`: o `title` de cada fatia nomeia o plástico, e
        # `title` não tem alvo no piloto — o bloco tem de nascer do produto.
        "regua-do-radio": _regua_do_radio(ctx),
        # AS TRÊS LISTAS SÃO O QUE A TELA MOSTRA, uma por bloco de achado: o
        # selo, a frase e o `?`. Elas se distribuem pelos elementos de mesmo
        # `data-campo`, na ordem — o gerador não precisa saber quantos achados
        # o exame vai devolver.
        "selo": [i["selo"] for i in itens],
        # O QUARTO SELO — decisão dela, 02/09/2026: *"o que está quebrado agora
        # não pode parecer igual ao que só podia estar melhor"*. O `Item` tem
        # QUATRO estados e a tela tinha TRÊS cores: `atencao` e  # (noqa-acento)
        # `problema`
        # caíam os dois na pílula laranja, pela mesma palavra do dono
        # (`SELO_DO_ESTADO`).
        #
        # O QUE VAI DAQUI É O ESTADO CRU, e não a classe CSS. Quem traduz
        # estado em cor é o DESENHO: cada pílula do gerador leva
        # `data-hef-alvo="classe" data-hef-classe="grave"
        # data-hef-quando="problema"`, e o `escrever()` do piloto acende a
        # classe na linha cujo estado casar (`hefesto_vivo.py:217`). Emitir a
        # classe daqui poria a folha de estilo dentro do Python, e amarraria o
        # pacote a um nome de classe que só o desenho conhece.
        #
        # A PALAVRA CONTINUA A MESMA, E É ESPERA DELA — ver `_selo_do_estado`.
        # Esta leva entrega a COR; o texto do quarto selo é decisão dela, e
        # escolhê-lo aqui seria escolher no lugar dela.
        #
        # SÃO QUATRO ENDEREÇOS, UM POR ESTADO — 03/09/2026. Ver
        # :func:`_selos_por_estado`: emitir o estado CRU num elemento que
        # pergunta *"é `problema`?"* era o pacote respondendo a outra pergunta,
        # e a régua do mockup acusava três endereços mortos por isso.
        #
        # OS TRÊS NOVOS SÓ ALCANÇAM A TELA DELA DEPOIS DA PUBLICAÇÃO: eles
        # existem na bancada (`mockup/08-conexoes.html`) e ainda não na página
        # publicada. Emitir antes não custa nada — o `achar()` do piloto não
        # encontra o endereço e escreve zero — e é o que faz a cor nascer certa
        # no minuto em que ela publicar.
        **_selos_por_estado(itens),
        # O `porque`, E NÃO O `rotulo` — corrigido em 02/09/2026, e a regra é do
        # produto: `gui.aba_conexoes.html_do_exame` diz, no docstring, *"O texto
        # é o `porque` — a MEDIÇÃO em uma frase —, nunca o rótulo: a tela
        # aprovada mostra o que se achou, não o nome do que se conferiu."*
        #
        # A tela desta aba estava mostrando o rótulo, e o rótulo é o NOME da
        # conferência. Fotografado com dois controles na mesa: as três linhas
        # diziam **"Economia de energia desligada"**, **"Energia das portas"** e
        # **"Suporte ao controle"** — três títulos de exame — onde o desenho
        # dela promete três achados. O `porque` dos mesmos três itens é
        # *"O sistema está proibido de desligar o rádio dos controles."*,
        # *"Conferido agora: nenhuma das 16 portas USB está em economia de
        # energia."* e *"A parte do sistema que fala com o DualSense está
        # carregada."*
        #
        # O `titulo` não se perdeu: ele é a primeira metade do `?`, que é onde a
        # `secao_exame` já o punha (`DICAS_DAS_LINHAS`, por chave de regra).
        "achado": [i["porque"] for i in itens],
        # O `?` DE CADA LINHA. **ELA PUBLICOU** — 02/09/2026, e o que estava
        # escrito aqui caducou no mesmo dia: dizia que *"a página PUBLICADA
        # ainda não tem `data-campo="achado-explica"`"*. Tem — as cinco linhas
        # da `interface/paginas/08-conexoes.html` o trazem, e a `08-conexoes`
        # saiu da `mockup/DIVERGENCIAS.md`. A dica desta aba é PINTADA hoje.
        "achado-explica": [i["dica"] for i in itens],
        # O CARIMBO do topo do Check-up — publicado no mesmo dia e pela mesma
        # decisão, e também já pintado.
        "examinado": _carimbo_do_exame(),
        "vizinho-nome": vizinho_nome,
        "vizinho-tipo": vizinho_tipo,
        "exame": itens,
        "achados": len(itens),
        "graves": sum(1 for i in itens if i["grave"]),
        "adaptadores": adap,
        "sem_driver": st.get("controles_sem_driver") or [],
        # SÓ O QUE ESTE TIQUE ACHOU SEM DONO — hoje só uma coisa entra aqui: uma
        # política de vibração guardada no perfil que o `<select>` da tela não
        # sabe mostrar. Declarar é o oposto de pintar a opção errada.
        "sem_dono": sem_dono,
        # O `+ len(itens) * 4` conta as QUATRO listas por achado (o selo, o
        # ESTADO do selo, a frase e o `?`), e o `+ 1` é o carimbo. Ela já
        # esteve em `* 3` com o selo e a frase sendo duas listas — contando
        # metade do que emitia —, e volta a errar assim toda vez que uma lista
        # nova por achado nascer e esta linha ficar para trás.
        #
        # ELA CONTA A MAIS, E ISSO ESTÁ MEDIDO — 02/09/2026. O
        # `sum(len(v) for v in colunas.values())` inclui `via`, `bateria`,
        # `ponte` e `fragil`, e a página publicada **não tem endereço para
        # nenhum dos quatro** (os treze `data-campo` dela estão listados no
        # relato desta leva). Eles não fazem mal — `achar()` não os encontra e
        # escreve zero —, mas somam quatro por controle a um número que se
        # chama "pintados". Este número é auto-relato: régua nenhuma o lê
        # (`pacotes.NAO_SAO_VALOR` o descarta antes da tela), e quem decide a
        # cobertura desta aba é a `--prova-de-mockup`, que lê a TELA. Fica dito
        # porque um número que se chama cobertura e não é foi o defeito que
        # esta casa mais pagou.
        "cobertura": {"pintados": 4 + len(itens) * 4 + 1 + len(adap)
                      + len(vizinho_nome) * 2
                      + sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO) + len(sem_dono)},
    }


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao daemon
# ---------------------------------------------------------------------------
# ESTA ABA É A DE MAIS BOTÕES DAS DEZ — 56 elementos ganharam `data-gesto` no
# gerador. A primeira leva (01/09, madrugada) ligou QUATRO e mediu o motivo dos
# outros um a um; esta segunda ligou mais QUATRO, e **duas das razões da
# primeira caducaram no mesmo dia**. Ficam escritas porque o que elas custaram
# é a lição:
#
#   1. **"o piloto só ouve `click`"** — CADUCOU. O ouvinte passou a escutar
#      `change` e a mandar `valor` e `rotulo` (`hefesto_vivo`, 01/09). Era essa
#      a trava de `mic-existe` e `vizinho-o-que-e`, e os dois estão ligados.
#      Restam nessa família só as duas CONTRADIÇÕES (`mic-escopo`,
#      `teto-da-vibracao`), que não eram problema de ouvinte nenhum.
#   2. **"o exame já roda a cada tique"** — ERA MEIA VERDADE, e a metade que
#      faltava era a que importava: rodavam três conferências das cinco, e
#      nenhuma ordem de serviço. As outras não cabem no tique (`pareamentos`
#      forka `busctl`), e é isso que dá trabalho ao "Examinar Portas" — que
#      agora o faz, e com ele o ⊘ ganhou sujeito.
#   3. **o gesto não é IPC** — continua valendo para "A luz não acende"
#      (`Disconnect` do BlueZ por D-Bus, `integrations/gesto_de_reconexao.py`).
#      **Mas não é motivo para não ligar**: o "Examinar Portas" também não é
#      IPC e está ligado. O que decide é haver um dono no produto, não ele estar
#      atrás do socket — e o `Disconnect` não tem dono chamável daqui.
#   4. **o dado da tela é do MOCKUP, não da mesa dela.** A pop-up "Mapear
#      Entradas" desenha `CENSO`, `FACES` e `QUEM_ESTA` — constantes do gerador.
#      Nenhuma delas é repintada pelo pacote. Um `machine.declare` disparado
#      dali gravaria no `maquina.json` DELA um mapa derivado de uma bancada de
#      exemplo. É o defeito mais caro que esta aba poderia cometer, porque o
#      arquivo que ele estragaria é o único que guarda o que só ela sabe.
#      **Foi exatamente essa a cura de `vizinho-o-que-e`**: em vez de ligar o
#      gesto sobre os quatro rádios do desenho, o pacote passou a PINTAR os
#      rádios dela por cima deles. O que muda um botão desta família de "não dá"
#      para "dá" é a tela deixar de ser exemplo.
from . import gesto  # noqa: E402

#: O QUE FOI MARCADO E **NÃO** FOI LIGADO, com o motivo medido de cada um. Esta
#: lista não é lápide: o piloto imprime `[gesto sem dono] 08-conexoes.html · X`
#: a cada clique nesses botões, e é assim que o que falta aparece na tela em vez
#: de sumir. Quem ligar um deles tira a linha daqui.
# `luz-nao-acende` SAIU DAQUI em 01/09/2026, e o que o segurava era uma
# conclusão, não um fato. A entrada dizia: *"`Disconnect` do BlueZ pelo D-Bus —
# `integrations/gesto_de_reconexao.py`, que roda `busctl` e não passa pelo
# daemon. Não há método IPC para isto."* As duas primeiras frases estão certas;
# a terceira é verdadeira e IRRELEVANTE — um gesto não precisa de IPC, precisa
# de quem faça. O `gesto_de_reconexao` faz, é puro, mascara o endereço e devolve
# a frase de tela pronta. Foi escrito para esta cura e nunca tinha sido chamado.
#
# É a mesma forma do `ver-detalhes` da aba Sistema, curado hoje de manhã: a nota
# dizia que ligá-lo *"exige o helper privilegiado ou um método de log que o
# daemon não tem"*, e bastava `journalctl --user`.
SEM_GESTO: dict[str, str] = {
    "mic-escopo":
        "CONTRADIÇÃO, e o ouvinte de `change` de 01/09 NÃO a desfaz: é "
        "`mic_button_toggles_system`, e o produto guarda UM por máquina "
        "(`daemon/lifecycle.py:272`), aplicado pelo rascunho do perfil "
        "(`ipc_draft_applier.py:592`) — não por controle, que é o que a tela "
        "oferece. Ligá-lo faria o segundo card sobrescrever a escolha do "
        "primeiro, calado. Declarada em `gui/aba_conexoes.SEM_FONTE`, linha "
        "`controle.*.mic.escopo`, com dona: MIGRA-CONEXOES-06, §0.7, palavra dela.",
    # `teto-da-vibracao` SAIU DAQUI em 01/09/2026, e o que o segurava era um
    # FATO ERRADO nas duas metades. A entrada dizia: *"a tela oferece um teto
    # POR CONTROLE e o produto aplica `min` global (`core/rumble.py`) — e o
    # `min` é justamente o que impede um 'teto' de AUMENTAR a força […]
    # sobrepor mudaria o DAEMON, não a tela."*
    #
    # O `min` de `core/rumble.py:108` compara a política GLOBAL com o teto do
    # ORÇAMENTO DA MESA — nenhum dos dois é por controle. E o caminho por
    # controle não passa por ali: ele é um FATOR aplicado um andar ABAIXO, em
    # `core/backend_pydualsense._escalar_rumble:3797-3818`, alimentado por
    # `profiles/manager._controllers_to_rumble_scales:1834` na ativação de
    # perfil. A cadeia inteira existe desde 10/08 (`POR-UNIDADE-01`) e chega ao
    # hardware. Sobrepor não muda uma linha do daemon.
    #
    # DUAS DAS TRÊS OPÇÕES ganharam fonte; a recusa que sobra é de UMA — o "Sem
    # teto" —, e ela mora DENTRO do gesto, com a razão medida. Ver
    # `gui/aba_conexoes.politica_do_rotulo` e a linha
    # `controle.*.vibracao.sem-teto` de `SEM_FONTE`.
    # OS SEIS DO MAPA SAÍRAM DAQUI em 01/09/2026, e a medição que os segurava
    # estava CERTA: *"a lista de aparelhos é a constante `CENSO` do gerador"*,
    # *"os quadrados saem de `FACES`/`QUEM_ESTA`"*, *"o desenho das faces é do
    # mockup, que o pacote não repinta"*. Enquanto isso valesse, clicar
    # declararia no `maquina.json` DELA o desenho de uma bancada de exemplo.
    #
    # A CURA FOI NO DESENHO, não nos botões: a aba passou a PINTAR o gabinete
    # dela (`_html_do_mapa`) e a lista de aparelhos do barramento dela
    # (`_html_dos_aparelhos`), com o desenho ÚNICO que o produto agora tem
    # (`gui/aba_conexoes.html_do_mapa`) e o motor de verdade
    # (`arranjo_da_mesa.julgar`, pelo `veredito_do_quadrado`). Com alvo real, os
    # seis passaram a poder agir.
    #
    # E A ÚLTIMA RAZÃO DA `nova-face` CAIU PELA RAIZ: dizia-se que
    # `fundir_declaracao` troca a lista de faces inteira e que criar uma
    # reescreveria as que já existem. Troca mesmo — e por isso o
    # `_gravar_o_mapa` manda o rascunho INTEIRO, que já contém as antigas.
    "novo-hub":
        "ele é o único dos sete que sobra, e por duas razões que não são de "
        "desenho. A primeira: `LogicaDoMapa` não tem `acrescentar_hub` — um hub "
        "de bancada não é entrada do gabinete, e o produto não tem campo para "
        "ele. A segunda está no próprio `title` do botão: ele promete "
        "*\"pergunta em que entrada ele está ligado\"*, e a tela não tem onde "
        "perguntar. Pendurá-lo no `acrescentar_extensao` faria o botão criar uma "
        "filha numa entrada que ela não escolheu.",
}


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa.

    O piloto traduz `pref` → `uniq` antes de chamar (`hefesto_vivo.py:556`); o
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


def _resposta(r: Any) -> tuple[bool, str]:
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


def _declarar(p: Any, mesa: dict[str, Any]) -> None:
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
def alvo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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
def todos(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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
def sala_altura(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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
def sala_visada(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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


def _chave_de_maquina(ctx: Contexto, uniq: str) -> str:
    """A chave deste controle no `maquina.json` — doze hexa, ou `""`.

    A REGRA É DO PRODUTO e a função é a dele
    (`app/actions/external_controllers.chave_de_maquina`): o schema exige doze
    hexa minúsculos sem separador e RECUSA O DOCUMENTO INTEIRO quando a chave
    não casa — um campo escrito errado vira "não consegui gravar", não "valor
    inválido".

    `""` PARA O ENDEREÇO QUE COMEÇA EM `02`, e essa recusa também é do schema: é
    o MAC que o `usb_probe_degrade` FORJA quando não há endereço, somando VID,
    PID e bus. Dois clones do mesmo modelo recebem o MESMO endereço forjado, e
    persistir isso gravaria em disco a FUSÃO de dois aparelhos.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.external_controllers import (
            chave_de_maquina,
        )

        entrada = dict(ctx.por_uniq(uniq) or {})
        entrada.setdefault("uniq", uniq)
        return chave_de_maquina(entrada) or ""
    except Exception:
        return ""


def _sem_endereco() -> str:
    """A frase do produto para "não há onde guardar isto".

    Ela é do `secao_controles`, e existe separada da do cabo de propósito: *"os
    dois motivos de estar apagado são diferentes e pedem frases diferentes: no
    cabo não FAZ FALTA, sem endereço não TEM ONDE ser guardada. Uma frase só
    para os dois mandaria a pessoa procurar cabo onde o problema é endereço."*
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_controles import (
            DICA_MIC_SEM_ENDERECO,
        )

        return str(DICA_MIC_SEM_ENDERECO)
    except Exception:
        # NÃO É CÓPIA DA FRASE DELE — é a minha, e diz a mesma coisa em outras
        # palavras. Repetir a dele aqui criaria a segunda verdade que a regra do
        # fato errado existe para matar.
        return ("mic-existe: este controle não tem endereço de doze hexa, e sem "
                "ele não há chave no maquina.json para guardar a ponte")


def _slot(o: dict[str, Any], quantos: int, quem: str) -> int:
    """A POSIÇÃO em que ela clicou, conferida contra o que foi pintado.

    O ouvinte do piloto manda `data-v`, e o gerador escreve nele o número da
    linha (`aba08.exame`, `aba08.viz_bloco`). Fora da faixa é clique numa linha
    que a pintura deixou vazia — o desenho tem cinco linhas de exame e quatro
    blocos de vizinho, e a mesa dela pode ter menos. Recusar dizendo é o que
    separa isto de agir sobre o vizinho errado.
    """
    bruto = str(o.get("v") or "")
    if not bruto.isdigit():
        raise ValueError(
            f"{quem}: o clique não disse em qual linha (data-v veio {bruto!r})")
    posicao = int(bruto)
    if not 0 <= posicao < quantos:
        raise RuntimeError(
            f"{quem}: esta linha está vazia — a tela tem o lugar e a sua mesa "
            f"tem {quantos} item(ns) aqui agora")
    return posicao


@gesto("08-conexoes.html", "mic-existe")
def mic_existe(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Microfone: Ligado / Desligado" — a ponte de mic DESTE controle.

    TEM DONO, E ELE NÃO É O `mic.set`. O `mic.set` é o MUDO no firmware
    (`ipc_handlers._handle_mic_set`): ele acende a luz vermelha e o PipeWire
    continua publicando a fonte. O que a tela promete aqui é outra coisa —
    *"Desligado, nenhum programa o enxerga"* — e isso é a PONTE, que existe ou
    não existe: `ControleDeclarado.microfone` no `maquina.json`
    (`utils/maquina.py:563`), decisão dela de 22/08/2026 (*"por controle"*).

    QUEM CONSOME, e é por isso que o clique vale AGORA: o
    `_handle_machine_declare` relê o disco, rebinda `daemon._maquina` e SOBE OU
    DESCE o subsystem `bt_mic` no mesmo pedido — a nota está no próprio handler
    (`ipc_handlers.py:5340`, QUATRO-MICROFONES-01): *"o 'Aplicar' tem de VALER
    agora"*. Sem essa parte, a escolha dela só valeria no próximo início do
    daemon.

    **DESLIGAR GRAVA `None`, NÃO `False`.** É regra do produto e está no
    `secao_controles._ao_alternar_o_microfone`: *"nunca pedi" e "não quero"
    deixam a ponte no chão do mesmo jeito, e um `false` em disco seria um valor
    de catálogo para o silêncio — a porta pela qual o default entra disfarçado
    de escolha dela*.

    O QUE ESTE GESTO **NÃO** ENTREGA, e a tela precisa dizer um dia: pelo CABO
    o microfone não passa por esta ponte. A frase é do produto
    (`secao_controles.DICA_MIC_NO_CABO`): *"Só vale no rádio. Pelo cabo o
    microfone deste controle é uma placa de som USB e não passa por esta ponte
    — ele já funciona sem ela."* A GUI estável apaga o interruptor no cabo
    (`pode_ligar_o_mic`); aqui ele grava, porque a declaração é sobre o
    CONTROLE e não sobre o transporte de agora — ela vale quando ele voltar
    para o rádio. O que fica devendo é o aviso na tela, e ele é da aba, não
    deste gesto.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("mic-existe: o clique não disse em qual controle")
    chave = _chave_de_maquina(ctx, uniq)
    if not chave:
        raise RuntimeError(_sem_endereco())
    escolha = str(o.get("valor") or o.get("rotulo") or "").strip()
    if escolha not in ("Ligado", "Desligado"):
        raise ValueError(f"mic-existe: {escolha!r} não é resposta desta lista")
    ligado = escolha == "Ligado"
    ok, motivo = _resposta(
        p.machine_declare({"controles": {chave: {"microfone": True if ligado else None}}}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o que você declarou")
    _reler_a_declaracao()


def _chave_no_perfil(ctx: Contexto, uniq: str) -> str:
    """A chave deste controle em ``Profile.controllers`` — doze hexa, ou ``""``.

    DUAS RÉGUAS, E AS DUAS TÊM DE CONCORDAR. A do PERFIL é `norm_mac` do
    esquema (`profiles/schema.py:1207`), que canoniza `aa:bb:…` em `aabbcc…`; a
    do `maquina.json` é `app.actions.external_controllers.chave_de_maquina`, que
    faz o mesmo e ainda RECUSA o MAC forjado que começa em `02` — o que o
    `usb_probe_degrade` inventa somando VID, PID e bus, e que dois clones do
    mesmo modelo compartilham. Persistir esse seria gravar a FUSÃO de dois
    aparelhos num perfil.

    E ELAS PODEM DIVERGIR, medido: `chave_de_maquina` usa o `identity` quando o
    daemon o carimbou (controles EXTERNOS, `external_key`), e o mapa que chega
    ao backend é chaveado pelo `uniq` (`set_rumble_scales`). Gravar sob a chave
    do `identity` produziria um override que o motor nunca casa — a escolha
    dela sumiria calada, que é o defeito mais caro desta casa. Quando as duas
    discordam, este gesto RECUSA em vez de gravar no lugar errado.

    MEDIDO no DualSense vivo dela em 01/09/2026: o item do `state_full` não
    traz `identity`, então `chave_de_maquina` cai no `uniq` e as duas coincidem.

    A NORMALIZAÇÃO É DO :func:`_so_hex`, e não escrita de novo aqui: a cópia
    literal que morava nesta linha era a chave que GRAVA, e a de
    `_teto_do_controle` era a que PINTA — duas grafias da mesma regra, já
    divergindo no `.strip()`.
    """
    da_maquina = _chave_de_maquina(ctx, uniq)
    if not da_maquina:
        return ""
    do_perfil = _so_hex(uniq)
    return do_perfil if do_perfil == da_maquina else ""


def _com_o_teto(prof: Any, chave: str, policy: str | None) -> Any:
    """O perfil com o teto DESTE controle trocado, ou ``None`` se nada mudou.

    ``None`` evita o barulho, e é a mesma razão de `_com_os_gatilhos`: regravar
    um perfil idêntico troca a data do arquivo e faz o daemon reaplicá-lo — e um
    `profile.switch` no meio de uma partida não é de graça.

    "SEGUE O GLOBAL" APAGA A SEÇÃO INTEIRA (``rumble=None``), e não grava
    ``policy=None``. `_controllers_to_rumble_scales` tem DOIS desvios seguidos:
    `cfg.rumble is None` (`profiles/manager.py:1862`) e `"policy" not in
    model_fields_set` (`:1864`). O primeiro é o que o esquema chama de "campo
    não escrito = sem opinião", e é o que o merge POR CAMPO promete
    (`ControllerRumbleOverride`, docstring). O segundo existe para um override
    que fale só de outra coisa — e `custom_mult` sem `policy='custom'` a borda
    já recusa, então apagar a seção é a única forma limpa de dizer "sem
    opinião" aqui.

    IGUAL AO GLOBAL TAMBÉM APAGA, e a regra é do produto:
    `app/draft_config.with_controller_rumble:1193-1223` já decidiu que
    "intensidade igual à global não vira override". A razão é aritmética:
    `_controllers_to_rumble_scales` calcula `mult / base` e DESCARTA o fator
    1,0 (`profiles/manager.py:1878-1879`) — guardar o override só deixaria no
    disco uma opinião que o motor ignora.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        ControllerRumbleOverride,
    )

    global_ = getattr(getattr(prof, "rumble", None), "policy", None)
    if policy is not None and policy == global_:
        policy = None

    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.rumble
    if policy is None:
        if antes is None:
            return None
        novo = None
    else:
        if antes is not None and antes.policy == policy:
            return None
        # `model_validate` E NÃO O CONSTRUTOR: quem decide se a política é
        # aceitável é a BORDA do esquema, não o tipo estático de quem chama —
        # é ela que recusa o `auto` por unidade COM a frase que explica
        # (`profiles/schema.py:800-811`). Construir com `policy=` obrigaria a
        # repetir aqui a lista de quatro literais, que é a segunda grafia que
        # esta leva inteira existe para matar.
        novo = ControllerRumbleOverride.model_validate({"policy": policy})
    atuais[chave] = dele.model_copy(update={"rumble": novo})
    return prof.model_copy(update={"controllers": atuais})


@gesto("08-conexoes.html", "teto-da-vibracao")
def teto_da_vibracao(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Teto da vibração: Segue o global / Sem teto / 30% da força" — POR CONTROLE.

    TEM DONO, E A CADEIA INTEIRA JÁ EXISTIA — `POR-UNIDADE-01`, 10/08/2026. O
    que este gesto grava é `controllers[chave].rumble.policy` no PERFIL, e daí
    em diante o produto faz sozinho: `_controllers_to_rumble_scales` converte em
    fator RELATIVO, `ProfileManager.apply:459-464` publica o mapa com
    `set_rumble_scales`, e `_escalar_rumble` multiplica o que vai ao motor nas
    duas rotas de escrita. Nenhum payload novo, nenhum IPC novo.

    A RECUSA QUE ESTAVA ESCRITA AQUI ERA UM FATO ERRADO nas duas metades, e a
    regra desta casa manda substituí-lo. Ela dizia que *"o produto aplica `min`
    (`core/rumble.py`), e o `min` é o que impede um 'teto' de AUMENTAR a
    força"*, e que *"sobrepor mudaria o daemon, não a tela"*. O `min` de
    `core/rumble.py:108` compara a política GLOBAL com o teto do ORÇAMENTO —
    nenhum dos dois é por controle —, e o caminho por controle passa um andar
    ABAIXO dele, em `core/backend_pydualsense._escalar_rumble:3797-3818`.

    "SEM TETO" CONTINUA RECUSANDO, e a recusa é a entrega: das três opções, é a
    única sem tradução honesta. `politica_do_rotulo` levanta com a razão medida,
    e este gesto não grava nada — a frase que falta é dela.

    É DO PERFIL, NÃO DA MÁQUINA. Sem perfil ativo não há onde guardar a força
    de um controle (`profiles/schema.py:1053`), e a recusa diz em que aba
    escolher um.

    FATO ERRADO, SUBSTITUÍDO no mesmo dia: esta linha dizia *"medido no daemon
    vivo dela em 01/09/2026: `active_profile = None`, logo é ESTA a resposta que
    a tela dela dá hoje"*. O daemon vivo responde `active_profile =
    'meu_perfil'`. Na mesa dela o gesto **não recusa: grava** — no perfil que ela
    está usando — e a `gravar_e_reaplicar` ainda dispara `profile.switch`, que
    reaplica o perfil inteiro. Quem lesse a linha velha concluiria que a feature
    está inerte quando ela é o oposto, e deixaria de conferir o que o motor
    recebe.
    """
    from hefesto_dualsense4unix.gui import aba_conexoes as _tela

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("teto-da-vibracao: o clique não disse em qual controle")
    chave = _chave_no_perfil(ctx, uniq)
    if not chave:
        # A FRASE É PRÓPRIA, e não a do microfone — 01/09/2026. Esta recusa
        # reusava `_sem_endereco()`, que fala de "a quem esta PONTE pertence":
        # ela escolhia um teto de vibração e a tela respondia sobre uma ponte
        # que ela não tocou, e num arquivo que este gesto nem escreve (o teto vai
        # para o PERFIL, a ponte para o `maquina.json`). É a mesma razão pela
        # qual o `_sem_endereco` existe separado da frase do cabo: dois motivos
        # diferentes pedem frases diferentes.
        raise RuntimeError(
            "este controle não tem endereço fixo de doze hexa, e sem ele não há "
            "chave no perfil para guardar a força só dele. Um controle sem "
            "endereço estável muda de nome a cada conexão, e a escolha cairia "
            "num aparelho diferente do que você está vendo.")

    escolha = str(o.get("valor") or o.get("rotulo") or "").strip()
    # A LISTA É A DA TELA, nunca três literais: `politica_do_rotulo` a lê de
    # `opcoes_do_teto()`, que é a mesma que o gerador desenhou. Foi assim que o
    # `mic-existe` se protegeu de um rótulo traduzido.
    policy = _tela.politica_do_rotulo(escolha)

    nome = str((ctx.state or {}).get("active_profile") or "").strip()
    if not nome:
        raise RuntimeError(
            "não há perfil ativo agora, e a força da vibração de um controle é "
            "do perfil — não da máquina. Escolha um perfil na aba Perfis e "
            "tente de novo.")

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    novo = _com_o_teto(prof, chave, policy)
    if novo is None:
        return
    perfil.gravar_e_reaplicar(novo, ctx, p)


@gesto("08-conexoes.html", "vizinho-o-que-e")
def vizinho_o_que_e(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"— O que é? —": ela responde o que é aquele rádio vizinho.

    TEM DONO: `MesaDeclarada.radios[vid:pid].tipo` (`utils/maquina.py:279`), e
    é o mesmo gesto do seletor da GUI estável
    (`secao_mesa._ao_declarar_o_radio:1486`). O Hefesto acha o aparelho no
    barramento e não sabe para que ele serve — a resposta é dela, e é ela que
    diz ao produto *o que dá para desligar e o que não dá*.

    A CHAVE É `vid:pid` E NÃO O NÓ DO SYSFS, e a razão é do produto: o nó muda
    de nome quando o aparelho troca de porta, e a resposta "isto é um teclado"
    não muda com a porta.

    O RÓTULO NÃO VAI CRU. `RadioDeclarado.tipo` é `Literal["wifi", "teclado",
    …]`; gravar "Caixa de som" faria o pydantic recusar o DOCUMENTO INTEIRO
    (`extra="forbid"` + `Literal`), e o sintoma na tela seria "não consegui
    gravar" em vez de "valor inválido" — a mesma armadilha que o
    `secao_mesa._valor_do_seletor` documenta. A tradução sai de
    `_TIPOS_DE_RADIO`, que é o dono dela.

    "— O que é? —" E "Não sei" VIRAM `None`, e é a mesma resposta: enquanto ela
    não responder, o produto NÃO sabe, e a tela diz isso em vez de chutar.
    """
    posicao = _slot(o, len(_VIZINHOS), "vizinho-o-que-e")
    chave = _VIZINHOS[posicao]
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    para_id, _ = _tipos_de_radio()
    if rotulo in ("", _a_pergunta()):
        tipo = None
    elif rotulo in para_id:
        tipo = para_id[rotulo]
        if tipo == "nao_sei":
            tipo = None
    else:
        raise ValueError(
            f"vizinho-o-que-e: {rotulo!r} não é uma das respostas do produto "
            f"({sorted(para_id)})")
    _declarar(p, {"radios": {chave: {"tipo": tipo}}})
    _reler_a_declaracao()


@gesto("08-conexoes.html", "examinar-portas")
def examinar_portas(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Examinar Portas": refaz o exame INTEIRO e a leitura do barramento.

    O QUE MUDOU DESDE A PRIMEIRA LEVA, e por isso ele deixa de ser botão morto:
    aqui estava escrito que *"o exame já roda a cada tique dentro de `_exame()`
    — o botão pediria de novo o que a aba refaz duas vezes por segundo"*. Isso
    era verdade sobre TRÊS conferências, e o exame tem cinco mais as ordens de
    serviço. As outras três nunca rodaram no tique porque não cabem nele:
    `pareamentos` forka `busctl` (teto de 5 s, `ESPERA_DO_BUSCTL_S`), e
    `ler_a_mesa` proíbe tique no próprio docstring.

    Então o botão faz exatamente o que o `title` dele promete — *"refaz o exame
    das entradas — energia e rádio — e repinta os selos, as linhas e as ordens
    de serviço"* — e é ele que traz o que o tique não pode trazer:

        pareamentos            `busctl`, os pareamentos salvos do BlueZ
        vizinhanca_das_portas  a linha que a altura da antena e a visada mudam
        ordens de serviço      `ordens_da_mesa.catalogo`, varredura do barramento
        os rádios vizinhos     `ler_a_mesa`, que endereça o "— O que é? —"

    ELE NÃO FALA COM O DAEMON, e é o único desta aba assim: o exame é sysfs +
    `busctl`, função pura sobre o sistema. Por isso está em `SEM_ECO` — não há
    campo do `state_full` que mude quando ele roda; o que muda é a tira do
    Check-up, no tique seguinte.

    RODA NA THREAD DO GESTO, que é onde o piloto o põe (`hefesto_vivo` dispara
    cada gesto num `threading.Thread`). É a mesma disciplina do
    `secao_exame.reexaminar`, e pela mesma cicatriz: um `subprocess.run`
    síncrono na thread do GTK congelou a janela inteira por 10 s.
    """
    global _EXTRAS, _QUANDO_O_EXAME
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import exame_da_mesa

    declaracao = _reler_a_declaracao()
    _dispensadas_do_disco(declaracao)
    _mesa_do_radio(recarregar=True)

    mesa = _mesa_declarada(declaracao)
    itens = exame_da_mesa.exame(
        # AS DUAS RESPOSTAS DELA ENTRAM AQUI, e não são enfeite: elas trocam a
        # linha `vizinhanca_das_portas` do próprio Check-up. É o que fecha o
        # laço dos gestos `sala-altura` e `sala-visada`, logo abaixo — o que
        # ela declarou muda o que o exame diz.
        altura_da_antena=mesa.get("altura_da_antena"),
        linha_de_visada=mesa.get("linha_de_visada"),
        # AS ORDENS DE SERVIÇO PRECISAM SER PEDIDAS, e o default é não pedir:
        # `exame_da_mesa.exame` explica que o catálogo varre o barramento
        # INTEIRO e que uma bancada de retrato não teria como substituí-lo. Aqui
        # a máquina é a dela, e é dela que a ordem tem de falar.
        leitura_das_ordens=exame_da_mesa.leitura_do_sistema,
    )
    if not itens:
        raise RuntimeError("não consegui examinar as entradas agora")
    _EXTRAS = tuple(itens)
    # O RELÓGIO DO CARIMBO, e ele só anda AQUI. As três conferências do tique
    # são refeitas duas vezes por segundo, então para elas a resposta honesta é
    # sempre "agora mesmo"; o que envelhece é o exame COMPLETO, que é este
    # botão. `monotonic` e não `time()`: o carimbo mede um INTERVALO, e um
    # acerto de relógio do sistema faria "há 3 minutos" virar "há mais de uma
    # hora" sem nada ter acontecido.
    _QUANDO_O_EXAME = time.monotonic()


@gesto("08-conexoes.html", "ignorar")
def ignorar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"⊘": cala ESTA ordem de serviço enquanto os cabos estiverem assim.

    TEM DONO: `MesaDeclarada.ordens_dispensadas[chave] = {quando, arranjo}`
    (`utils/maquina.py:280`), o mesmo que `secao_exame._gravar_a_dispensa:995`
    escreve.

    **A CHAVE DA DISPENSA É O ARRANJO, NÃO A RECOMENDAÇÃO** — e é o que impede
    que este botão vire "grava e não cala". `ordens_da_mesa.ordens_novas:850`
    compara o arranjo GUARDADO com o de agora; uma dispensa gravada com
    `arranjo=""` passaria no esquema e nunca casaria, e a linha voltaria no
    tique seguinte. Foi essa medição que manteve o ⊘ sem dono na primeira leva,
    e o que mudou não foi o esquema: é que agora existe `Item.ordem` na tela,
    porque o **Examinar Portas** traz o catálogo.

    UMA CONFERÊNCIA NÃO SE DISPENSA. As linhas `energia_do_radio`,
    `pareamentos`, `suporte_ao_controle`… respondem *"está certo?"*; só uma
    ORDEM responde *"faça isto"*, e só ela tem arranjo. O ⊘ numa conferência
    recusa dizendo — gravar ali criaria uma chave que regra nenhuma consulta.

    `quando` É SÓ A DATA. A hora não muda decisão nenhuma do produto e é um dado
    a mais sobre a rotina dela num arquivo que ela cola em relato de defeito —
    `OrdemDispensada._so_a_data` reprova qualquer outra forma.

    E A LINHA CALA NA HORA: a dispensa entra em `_DISPENSADAS` antes de o
    próximo tique montar a tira. Esperar o disco significaria a linha piscando
    de volta meio segundo depois do clique dela.
    """
    from datetime import date

    posicao = _slot(o, len(_ORDENS_NA_TELA), "ignorar")
    ordem = _ORDENS_NA_TELA[posicao]
    if ordem is None:
        raise RuntimeError(
            "ignorar: esta linha é uma CONFERÊNCIA, não uma ordem de serviço — "
            "ela responde \"está certo?\" e não há o que dispensar. Só as "
            "linhas 'Mudança recomendada' se calam, e elas aparecem depois de "
            "\"Examinar Portas\".")
    _declarar(p, {"ordens_dispensadas": {
        str(ordem.chave): {"quando": date.today().isoformat(),
                           "arranjo": str(ordem.arranjo)}}})
    _DISPENSADAS[str(ordem.chave)] = str(ordem.arranjo)
    _reler_a_declaracao()


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
# ---------------------------------------------------------------------------
# OS SEIS DO MAPA DO GABINETE — 01/09/2026
# ---------------------------------------------------------------------------
# TODOS PASSAM PELA MESMA CAMADA, e ela já existia: `LogicaDoMapa`, em
# `app/widgets/mapa_da_mesa.py`, cujo docstring diz *"o rascunho do gabinete e
# os quatro gestos que o mudam — sem GTK"*. Ela nunca tinha sido chamada por
# tela nenhuma.
#
# O QUE OS SEGURAVA ERA O DESENHO, e a medição estava certa: enquanto as faces
# e as entradas eram `FACES`/`QUEM_ESTA` — constantes de bancada —, clicar
# declararia no `maquina.json` DELA o desenho de um exemplo. A cura foi a aba
# passar a PINTAR o gabinete dela (ver `_html_do_mapa`); os botões vieram junto.
#
# O RASCUNHO É UM SÓ (`_logica_do_mapa`), e é ele que guarda o aparelho na mão
# entre o primeiro e o segundo tempo. Cada gesto muda o rascunho e GRAVA —
# decisão dela, 01/09: *"clicar na cor já deveria aplicar a cor no controle"*.
#
# OS CINCO QUE GRAVAM SÃO **SEM ECO**, e isso foi MEDIDO em 02/09/2026, não
# deduzido: as chaves de topo do `state_full` do daemon vivo são 47, e nenhuma
# delas é `mapa` nem `maquina`. O caminho é `machine_declare` →
# `_handle_machine_declare` (`daemon/ipc_handlers.py:5258`) → `maquina.json`, e
# ali ele PARA. Nada volta pelo estado. Ver a nota do `SEM_ECO`, no fim deste
# arquivo, para o que isso significa para quem lê a régua do piloto.


def _gravar_o_mapa(p: Any) -> None:
    """Manda ao daemon o rascunho inteiro do mapa, e RECUSA DIZENDO se não deu.

    O MAPA VAI INTEIRO, ao contrário da mesa (`_declarar`, que manda pedaço): as
    faces são uma LISTA, e `fundir_declaracao` troca lista inteira em vez de
    fundir (`utils/maquina.py`). Mandar meia lista apagaria as faces que ela já
    tinha — e era uma das razões escritas para `nova-face` não ser ligada.

    Mandar o rascunho INTEIRO resolve isso pela raiz: o que sai daqui é o estado
    completo do mapa depois do clique, e a troca de lista passa a ser o
    comportamento certo em vez de um risco.
    """
    ok, motivo = _resposta(p.machine_declare({"mapa": _logica_do_mapa().como_documento()}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o desenho do gabinete")


@gesto("08-conexoes.html", "escolher-aparelho")
def escolher_aparelho(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Primeiro tempo: o aparelho vai para a mão dela. Clicar de novo desescolhe.

    NÃO GRAVA NADA, e é o único dos seis que não grava: escolher é estado de
    tela, não declaração. O que vai ao disco é o SEGUNDO tempo.

    E É POR ISSO QUE ELE ESTÁ NO `SEM_ECO` COM RAZÃO DIFERENTE DOS OUTROS
    CINCO: eles não ecoam porque o `state_full` não publica o `mapa`; ESTE não
    ecoa porque não chama a ponte de forma nenhuma — medido com dublê em
    02/09/2026, o clique dirigido (`caminho="3-1.1.4"`) fez ZERO chamadas.
    Um gesto de meio-caminho é o que o `escolhido` guarda, e guardar é tudo o
    que ele tem a fazer.

    O ENDEREÇO É O CAMINHO DO KERNEL (`data-caminho`), e não o rótulo: os dois
    adaptadores Bluetooth desta bancada são o mesmo modelo, e `rotulo_do_aparelho`
    já explica que só o caminho os distingue.
    """
    caminho = str(o.get("caminho") or "").strip()
    if not caminho:
        raise ValueError(
            "o clique não disse qual aparelho — sem o caminho do kernel, dois "
            "adaptadores iguais seriam o mesmo botão.")
    _logica_do_mapa().escolher(caminho)


@gesto("08-conexoes.html", "escolher-entrada")
def escolher_entrada(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Segundo tempo: põe nesta entrada o aparelho que está na mão.

    SEM APARELHO NA MÃO, RECUSA DIZENDO. O desenho já ensina o gesto de dois
    tempos, e um clique na entrada sem ter escolhido antes não tem o que fazer —
    engolir isso faria a pessoa clicar dez vezes achando que o mapa quebrou.

    UM APARELHO ESTÁ EM UM LUGAR SÓ: `colocar` tira de onde estava no mesmo
    gesto, e a razão está escrita lá — *"sem isso o mesmo dongle apareceria em
    duas entradas e o mapa passaria a mentir de um jeito novo"*.
    """
    numero = str(o.get("entrada") or "").strip()
    if not numero:
        raise ValueError("o clique não disse qual entrada.")
    logica = _logica_do_mapa()
    if not logica.escolhido:
        raise RuntimeError(
            "escolha antes o aparelho, na lista de cima — este gesto tem dois "
            "tempos: primeiro o que vai, depois onde vai.")
    if not logica.colocar(numero):
        raise RuntimeError(
            f"não consegui pôr o aparelho na entrada {numero} — ela não está no "
            f"desenho do gabinete.")
    _gravar_o_mapa(p)


@gesto("08-conexoes.html", "tirar-daqui")
def tirar_daqui(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Esvazia a entrada. Ela CONTINUA no desenho — só fica sem aparelho.

    É o que o `title` do botão promete, e a diferença importa: tirar a ENTRADA
    seria outro gesto, e o gabinete não perde um buraco porque ela desplugou
    algo dele.
    """
    numero = str(o.get("entrada") or "").strip()
    if not numero:
        raise ValueError("o clique não disse de qual entrada tirar.")
    if not _logica_do_mapa().tirar(numero):
        raise RuntimeError(f"a entrada {numero} já está vazia.")
    _gravar_o_mapa(p)


@gesto("08-conexoes.html", "nova-entrada")
def nova_entrada(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Acrescenta a esta face o menor número que ainda não existe em face nenhuma.

    A REGRA DO NÚMERO É DO PRODUTO (`acrescentar_entrada`), e ela é o motivo de
    o botão não perguntar nada: os números são do GABINETE, e dois buracos
    diferentes não podem levar o mesmo.
    """
    face = str(o.get("face") or "").strip()
    if not face.isdigit():
        raise ValueError("o clique não disse em qual face acrescentar.")
    if not _logica_do_mapa().acrescentar_entrada(int(face)):
        raise RuntimeError("não achei essa face no desenho do gabinete.")
    _gravar_o_mapa(p)


@gesto("08-conexoes.html", "nova-extensao")
def nova_extensao(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Cria a entrada-filha desta: a `10` vira `10a`, depois `10b`. Não há neta.

    A EXISTÊNCIA DO EXTENSOR É DECLARAÇÃO DELA, e não há como ser outra coisa:
    cabo passivo não tem descritor USB, e o dongle na ponta enumera como se
    estivesse na entrada do hub. Nenhuma leitura de `/sys`, hoje ou nunca,
    distingue os dois casos.
    """
    numero = str(o.get("entrada") or "").strip()
    if not numero:
        raise ValueError("o clique não disse em qual entrada há a extensão.")
    if not _logica_do_mapa().acrescentar_extensao(numero):
        raise RuntimeError(
            f"não dá para pendurar uma extensão na {numero}: ou ela não está no "
            f"desenho, ou já é filha de outra — não há neta.")
    _gravar_o_mapa(p)


@gesto("08-conexoes.html", "nova-face")
def nova_face(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Cria uma face com o nome que ela escreveu. Sem nome, não cria.

    O NOME CHEGA EM `valor`, e é o que mudou em 01/09/2026: o ouvinte do piloto
    passou a mandar o `value` do campo. Antes só chegava `texto`, que num
    `<input>` é vazio — e era essa a primeira razão de este botão não ter dono.

    A SEGUNDA RAZÃO CAIU JUNTO: dizia-se que `fundir_declaracao` troca a lista
    de faces inteira e que criar uma reescreveria as que já existem. Troca
    mesmo — e por isso o `_gravar_o_mapa` manda o rascunho INTEIRO, que já
    contém as antigas mais a nova.
    """
    nome = str(o.get("valor") or "").strip()
    if not nome:
        raise ValueError(
            "a face precisa de um nome — escreva no campo ao lado antes de "
            "clicar. Sem nome, não cria.")
    if not _logica_do_mapa().acrescentar_face(nome):
        raise RuntimeError("não consegui criar a face.")
    _gravar_o_mapa(p)


@gesto("08-conexoes.html", "luz-nao-acende")
def luz_nao_acende(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Derruba este controle do rádio para ela apertar PS e a luz voltar.

    O QUE ELE CURA, e o desenho já o dizia: no Bluetooth a barra de luz pode
    parar de obedecer, e o caminho de volta é a RECONEXÃO — cair do rádio e
    entrar de novo pelo botão PS.

    NÃO É IPC, E NÃO PRECISA SER. O `Disconnect` é do BlueZ, pelo D-Bus, e o
    produto já tem quem o peça: `integrations/gesto_de_reconexao.desconectar`,
    que é puro (o `busctl` entra por argumento), mascara o endereço em todo log
    e devolve a frase de tela pronta em português. Foi escrito para esta cura e
    nunca tinha sido chamado por tela nenhuma.

    A RECUSA DO CABO É DO DESENHO, não minha: o `title` do botão apagado diz
    *"Este controle está no cabo, onde a barra de luz não depende de reconexão
    nenhuma"*. Derrubar um controle que está no cabo não o derruba — e um botão
    que aceita o clique e não faz nada é o que responde calado.

    OS QUATRO DESFECHOS VIRAM DOIS, e a linha que os separa é do módulo:
    `Resultado.caiu` conta `desconectou` E `ja_estava_fora` como sucesso, porque
    *"para quem espera o botão PS, os dois estados pedem exatamente o mesmo
    gesto"*. `nao_deu` e `sem_alvo` são "não sei" e "não achei", e os dois
    LEVANTAM com a frase que o módulo escreveu.

    O ENDEREÇO NUNCA APARECE INTEIRO. O `Resultado.endereco` já vem mascarado, e
    é ele que entra na frase — nesta casa há dois portões que reprovam um MAC de
    doze hexa em arquivo versionado, e uma exceção de tela vira log.

    ESTE GESTO NÃO ENTRA NO `SEM_ECO`, E ISSO É DE PROPÓSITO — 02/09/2026.
    Ele é o único dos sete acusados que TEM eco, e o eco é o maior desta aba:
    derrubar um controle do rádio o tira da lista `controllers` do `state_full`.
    Declará-lo sem eco cegaria a régua exatamente onde ela mais enxerga — um
    "Disconnect" que não derruba nada passaria a contar como sucesso.

    E A RECUSA MEDIDA EM 02/09 ESTAVA CERTA. A régua do piloto clicou este botão
    com o controle do CABO e leu "sem efeito"; o gesto tinha levantado a frase
    acima. **Não conserte isto.** O que faltou foi o instrumento passar o alvo,
    e um `RuntimeError` explicando o cabo é o comportamento contratado.
    """
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

    uniq = _uniq(o)
    if not uniq:
        raise ValueError(
            "o clique não disse em qual controle — a luz é de um aparelho, não "
            "da mesa.")
    dele = ctx.por_uniq(uniq)
    transporte = str(dele.get("transport") or "").lower()
    if transporte and transporte != "bt":
        raise RuntimeError(
            "este controle está no cabo, e no cabo a barra de luz não depende "
            "de reconexão nenhuma. A cura é do rádio: derrubar a conexão para "
            "você apertar PS.")

    resultado = radio.desconectar(uniq)
    if not resultado.caiu:
        raise RuntimeError(resultado.porque)


PONTE = {"chamar", "machine_declare"}
METODOS = {"controller.target.set"}


#: O QUE ESTA ABA DECLARA À RÉGUA — o piso e as provas moram AQUI, e não no
#: teste, para que ligar uma aba não exija editar um arquivo que oito pessoas
#: editariam ao mesmo tempo.
PAGINA = "08-conexoes.html"
PISO_DA_ABA = 16
PROVAS = [
    # O `index` da prova é 0 porque o controle de mentira é o único da lista —
    # e o `_indice` cai na posição quando o daemon não publicou `index`.
    {"pagina": PAGINA, "gesto": "alvo", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["controller.target.set"], {"index": 0})]},
    # SEM `uniq` no clique de propósito: "todos" não tem sujeito, e a régua
    # prova que ele não passa a exigir um.
    {"pagina": PAGINA, "gesto": "todos", "clique": {"uniq": "", "controle": ""},  # (noqa-acento) id
     "chama": [("chamar", ["controller.target.set"], {"index": None})]},
    {"pagina": PAGINA, "gesto": "sala-altura", "clique": {"modo": "acima"},  # (noqa-acento) id
     "chama": [("machine_declare", [{"mesa": {"altura_da_antena": "acima"}}], {})]},
    # "Não sei" chega como `""` e tem de virar `None` — a string `"nao_sei"`
    # derrubaria o documento inteiro no pydantic.
    {"pagina": PAGINA, "gesto": "sala-visada", "clique": {"modo": ""},  # (noqa-acento) id
     "chama": [("machine_declare", [{"mesa": {"linha_de_visada": None}}], {})]},
    # O `uniq` da régua (`aa:bb:cc:00:00:01`) vira a chave `aabbcc000001` pela
    # função DO PRODUTO — doze hexa minúsculos sem separador, que é o que o
    # schema exige. A prova cobre a conversão junto com a chamada: um gesto que
    # mandasse o MAC com dois-pontos derrubaria o documento inteiro no pydantic
    # e a tela diria "não consegui gravar".
    {"pagina": PAGINA, "gesto": "mic-existe", "clique": {"valor": "Ligado"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": True}}}], {})]},
    # DESLIGAR GRAVA `None`, NUNCA `False`, e é a prova de que a regra do
    # produto atravessou: um `false` em disco seria um valor de catálogo para o
    # silêncio (`ControleDeclarado`, `secao_controles._ao_alternar_o_microfone`).
    {"pagina": PAGINA, "gesto": "mic-existe", "clique": {"valor": "Desligado"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": None}}}], {})]},
]

#: OS GESTOS SEM PROVA AQUI, e o motivo é o limite desta régua — não é
#: descuido, e por isso está escrito:
#:
#:     os SEIS do mapa    dependem do `_logica_do_mapa()`, que é montado a
#:     do gabinete        partir do `maquina.json` DE QUEM RODA a régua. O
#:                        payload de `machine_declare` é o gabinete inteiro:
#:                        cravá-lo aqui faria a prova passar nesta bancada e
#:                        reprovar em qualquer outra — a mesma razão que
#:                        mantém `vizinho-o-que-e` fora. A prova deles injeta
#:                        um gabinete de bancada no `_LOGICA` e está em
#:                        `tests/unit/test_os_sete_de_conexoes_recusam_dizendo.py`,
#:                        junto com a recusa de cada um.
#:
#:
#:     examinar-portas    não chama a ponte. Ele é sysfs + `busctl`, e a régua
#:                        mede QUAL função da ponte o gesto chamou.
#:     ignorar            precisa de uma ordem de serviço na tela, e ela só
#:                        existe depois de o exame COMPLETO rodar.
#:     vizinho-o-que-e    precisa dos rádios vizinhos lidos do `/sys` dela.
#:     teto-da-vibracao   exige PERFIL ATIVO, e o `ctx` desta régua não tem um.
#:                        Mesma razão de `a06_navegacao.padrao-definicoes` e de
#:                        `a03_gatilhos.guardar`, que também ficam fora. A prova
#:                        dele é o disco, e está em
#:                        `tests/unit/test_o_teto_da_vibracao_e_por_controle.py`,
#:                        com perfil descartável e ponte dublê.
#:
#: Os dois últimos poderiam ganhar prova de UM jeito só: fazendo a régua varrer
#: o barramento da máquina que a roda. Isso é o oposto do que esta casa faz —
#: seria um teste unitário lendo `/sys`, verde nesta bancada e vermelho em
#: qualquer CI, e um portão que depende do hardware de quem o roda não mede
#: nada. **A prova deles foi feita à parte**, com a leitura real e uma ponte
#: dublê, e está no relato desta leva: o `ignorar` gravou
#: `teclado_so_no_hub` com o arranjo `3-1.1.2`, e o `vizinho-o-que-e` traduziu
#: "Caixa de som" em `caixa_de_som` sobre o rádio `046d:08e5`.

#: OS QUE GRAVAM NO DISCO, e não no daemon — o `state_full` não republica nada
#: disto. "O dongle fica acima da cabeça?" e "há gente entre ele e o sofá?" são
#: coisas que barramento nenhum responde; a ponte de microfone, o tipo do rádio
#: vizinho e a dispensa de uma ordem são decisões DELA. Todos vão para o
#: `maquina.json` (`utils/maquina.py`).
#:
#: A prova deles é o ARQUIVO, não o estado — com uma exceção que vale dizer: o
#: `mic-existe` TEM efeito vivo, porque o `_handle_machine_declare` sobe ou desce
#: o subsystem `bt_mic` no mesmo pedido; o que ele não tem é ECO, porque o
#: `state_full` não publica quem está declarado.
#:
#: `examinar-portas` está aqui pelo motivo oposto: ele não toca o daemon de
#: forma nenhuma. O que ele muda é a tira do Check-up, no tique seguinte — uma
#: régua que só olhasse o daemon diria "sem efeito" sobre o botão que trocou o
#: diagnóstico inteiro da tela.
#:
#: `teto-da-vibracao` grava no PERFIL, e não no `maquina.json` como os outros —
#: mas está aqui pelo mesmo motivo de fundo: o `state_full` não publica override
#: por controle nenhum, então a prova dele também é o ARQUIVO. Ele TEM efeito
#: vivo (o `profile.switch` de `gravar_e_reaplicar` faz `ProfileManager.apply` publicar
#: as escalas no backend); o que ele não tem é ECO.
#: OS SEIS DO MAPA DO GABINETE ENTRARAM EM 02/09/2026, e a razão de cada um
#: está escrita porque `SEM_ECO` sem razão é lápide para esconder defeito.
#:
#: A MEDIÇÃO QUE OS PÔS AQUI — dublê da ponte, nenhum comando ao daemon vivo:
#:
#:     gesto              clique cego          clique dirigido       chamou
#:     escolher-aparelho  ValueError           ACEITOU               NADA
#:     escolher-entrada   ValueError           RuntimeError (1º tempo)  —
#:     tirar-daqui        ValueError           ACEITOU               machine_declare
#:     nova-entrada       ValueError           ACEITOU               machine_declare
#:     nova-extensao      ValueError           ACEITOU               machine_declare
#:     nova-face          ValueError           ACEITOU               machine_declare
#:
#: `escolher-aparelho` — o ÚNICO que não chama a ponte. Ele é o primeiro tempo
#: do gesto de dois: guarda o aparelho na mão (`LogicaDoMapa.escolhido`) e para
#: aí. Não há o que ecoar porque não há o que gravar.
#:
#: `escolher-entrada` · `tirar-daqui` · `nova-entrada` · `nova-extensao` ·
#: `nova-face` — os cinco gravam `{"mapa": …}` pelo `_gravar_o_mapa`, e o
#: `state_full` NÃO PUBLICA O MAPA. Medido contra o daemon vivo em 02/09: 47
#: chaves de topo, e nem `mapa` nem `maquina` está entre elas. O desenho do
#: gabinete DELA é declaração em disco, não estado de aparelho — barramento
#: nenhum devolve "quantas faces tem o seu gabinete". A prova deles é o
#: ARQUIVO, e está em `tests/unit/test_o_mapa_do_gabinete_e_o_dela.py`.
#:
#: E FICA O AVISO PARA QUEM LER A RÉGUA DO PILOTO: "sem efeito e sem `SEM_ECO`"
#: NÃO quer dizer "disse aplicado". `_depois_do_gesto`
#: (`interface/hefesto_vivo.py`) compara o estado do daemon antes e depois do
#: clique e NÃO consulta se o gesto levantou — quando ele levanta, o piloto
#: imprime `[gesto falhou]` no stderr e `self.aplicados` não recebe nada. Um
#: gesto que RECUSOU DIZENDO cai na mesma lista de um que mentiu. Foi assim que
#: os sete desta aba entraram na conta dos "dezesseis aplicados que não
#: aplicam" de 02/09: eles recusaram, com frase, porque o clique automático não
#: levava o argumento do próprio botão (`caminho`, `entrada`, `face`, `uniq`).
SEM_ECO = ("sala-altura", "sala-visada", "mic-existe", "vizinho-o-que-e",
           "ignorar", "examinar-portas", "teto-da-vibracao",
           "escolher-aparelho", "escolher-entrada", "tirar-daqui",
           "nova-entrada", "nova-extensao", "nova-face")
