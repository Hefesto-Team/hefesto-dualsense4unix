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
import html
import re
import time
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

from . import TODOS_OS_LUGARES, Contexto, perfil, registrar

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
#:
#: **O ARRANJO VAZIO É O DESFAZER, e não um estado inválido** — 06/09/2026,
#: `ONDA5-08-01`. `machine.declare` não tem verbo de remoção: a fusão do daemon
#: desce nos dicionários aninhados e só a AUSÊNCIA de uma chave preserva o que
#: havia (`utils/maquina.py`, `fundir_declaracao`), então mandar o dicionário
#: menos uma chave NÃO apaga a chave. O que apaga o EFEITO é gravar
#: `arranjo=""`: `ordens_da_mesa.ordens_novas` compara o arranjo guardado com o
#: de agora, e um vazio guardado não casa com arranjo nenhum — a ordem volta a
#: falar. A propriedade que o `ignorar` descrevia como DEFEITO até 05/09 (*"uma
#: dispensa gravada com `arranjo=\"\"` passaria no esquema e nunca casaria"*) é
#: o mecanismo do desfazer.
_DISPENSADAS: dict[str, str] = {}

#: O QUE ACONTECE COM UMA ORDEM QUE ELA MANDOU IGNORAR — a MEDIÇÃO, não a
#: promessa. **O DONO MUDOU DE ARQUIVO EM 06/09/2026**, e a razão é de direção:
#: a frase deixou de ser só desenho e passou a ser PINTADA (o `title` do ⊘ é
#: `data-campo="ignorar-dica"`), e o gerador pode importar o pacote — o pacote
#: não pode importar o gerador, que escreve a bancada ao ser importado. Quem
#: pinta é dono; `aba08.ORDEM_IGNORADA_VOLTA` passou a ler daqui.
#:
#: **FATO ERRADO, SUBSTITUÍDO** (a nota de 04/09 continua valendo): a quinta
#: linha do Check-up dizia *"elas voltam em **Ver as ordens ignoradas**"*, e o
#: botão saiu da tela em 31/08 — a frase mandava ela procurar um botão que não
#: existe.
ORDEM_IGNORADA_VOLTA = "volta sozinha se o arranjo dos cabos mudar"

#: OS DOIS VERBOS DO ⊘ — decisão **08-Q5** dela, 05/09/2026: *"A recomendação
#: calada continua no lugar dela, em cinza, e o mesmo botão desfaz."*
#:
#: **O `title` DO DESENHO PASSA A SER SÓ O DE PARTIDA.** Até 05/09 ele era
#: cravado no gerador e mentia por construção: dizia *"A recomendação sai desta
#: lista"*, e a decisão dela põe a linha de volta na lista. Pior, ele dizia a
#: mesma coisa depois do clique — um botão que muda de sentido com uma dica que
#: não muda é a cicatriz da trava da luz, medida em 04/09.
#:
#: **A LISTA VAI EM TODO TIQUE, inclusive com a linha falando** — é a mesma
#: regra do botão cinza da ONDA0-F: a chave que só aparece quando há o que
#: dizer deixa na tela a tinta do tique anterior.
DICA_DO_IGNORAR = ("Ignora ESTE conselho enquanto os cabos estiverem assim. "
                   f"A recomendação fica em cinza nesta lista e {ORDEM_IGNORADA_VOLTA}.")

#: O SEGUNDO VERBO, palavra dela na 08-Q5: *"o mesmo botão desfaz"*.
DICA_DO_DESFAZER = "Traz esta recomendação de volta para a lista."

#: O EXAME DE ENTRADA JÁ FOI PEDIDO NESTA SESSÃO? — 03/09/2026, `MIGRA-08-01`.
#: Ele é UMA VEZ SÓ e não se re-arma: o que o rearmaria é o botão **Examinar
#: Portas**, que é gesto dela. Sem esta trava, um exame que falha viraria um
#: `busctl` novo a cada 500 ms — a tela pediria ao sistema duas vezes por
#: segundo o que ele acabou de recusar.
_EXAME_PEDIDO: bool = False

#: OS APELIDOS DOS ADAPTADORES, lidos do BlueZ. **Forka `busctl`**, e por isso
#: entra na mesma regra do `_MESA_DO_RADIO`: uma leitura, renovada pelo
#: **Examinar Portas**. Medido nesta bancada em 04/09/2026: `ler_os_dongles()`
#: custa **21,8 ms** e devolve os três adaptadores dela com o nome que ela
#: escreveu. A 500 ms de tique isso seria um fork a cada meio segundo contra o
#: BlueZ — o preço que o bloco acima proíbe.
#:
#: `None` = ainda não lido, ou a leitura falhou; e o `None` é diferente de uma
#: tupla vazia: "não perguntei ao BlueZ" não pode virar "nenhum adaptador tem
#: nome", que é a ausência de notícia lida como fato.
_DONGLES: Any = None

#: A ÚLTIMA SONDA DA MESA SUJA, e ela é `(quando, resposta)`. A resposta é a de
#: `secao_controles._pergunta_da_mesa()` — `True`/`False`/`None`, e o `None` é
#: "não consegui olhar", que NUNCA vira aviso.
#:
#: POR QUE UM CACHE DE 2 s E NÃO O DO PRODUTO: a sonda já tem um cache de 5 s
#: para a lista de PIDs da Steam (`escritor_cru.VALIDADE_DO_VEREDITO_S`), mas a
#: varredura de `/proc/<pid>/fd` roda **a cada chamada** quando a Steam está de
#: pé. Medido com a Steam fechada: 67 ms na primeira e 0,0 ms depois. Com ela
#: aberta o custo é o da varredura, e um tique de 500 ms o pagaria duas vezes
#: por segundo. Dois segundos é curto o bastante para ela fechar a Steam e ver a
#: dica mudar, e longo o bastante para não pendurar a varredura no tique.
_MESA_SUJA: tuple[float, bool | None] | None = None

#: Quanto vale a sonda da mesa suja, em segundos. Ver :data:`_MESA_SUJA`.
VALIDADE_DA_MESA_SUJA_S = 2.0


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


def _dongles(recarregar: bool = False) -> Any:
    """Os adaptadores pela ótica do BlueZ — endereço, alias e o nome DELA.

    É a única fonte do **nome** de um adaptador: o sysfs não publica o endereço
    (medido em 22/08, `/sys/class/bluetooth/hci0/` não tem `address`) e o
    apelido mora no `org.bluez.Adapter1.Alias`, não no `maquina.json` — está
    escrito em `secao_mesa`: *"o alias mora no BlueZ, que não passa pelo
    rascunho da máquina"*.

    `None` quando não deu para perguntar, e ele é diferente de `()`: sem
    resposta a coluna Nome fica com a palavra do produto (**Sem nome**) em vez
    de afirmar que ela não deu nome a nenhum.
    """
    global _DONGLES
    if _DONGLES is None or recarregar:
        try:
            perfil._com_o_src()
            from hefesto_dualsense4unix.integrations.apelido_do_dongle import (
                ler_os_dongles,
            )

            _DONGLES = tuple(ler_os_dongles())
        except Exception:
            return None
    return _DONGLES


def _mesa_suja() -> bool | None:
    """Alguém está segurando nó de controle AGORA? `None` = não consegui olhar.

    O DONO DA PERGUNTA É `secao_controles._pergunta_da_mesa`, e as três
    respostas são de propósito — a terceira é a que importa: um "não sei" não
    vira aviso, *"porque alarme sem medição atrás ensina a ignorar alarme"*.

    O CACHE É DAQUI E O MOTIVO ESTÁ EM :data:`_MESA_SUJA`: a sonda é a única
    coisa desta aba que responde a algo que ela pode MUDAR no meio da sessão
    (fechar a Steam), então não cabe na regra do "lê uma vez e o botão renova".
    """
    global _MESA_SUJA
    agora = time.monotonic()
    if _MESA_SUJA is not None and (agora - _MESA_SUJA[0]) < VALIDADE_DA_MESA_SUJA_S:
        return _MESA_SUJA[1]
    resposta: bool | None = None
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_controles import (
            _pergunta_da_mesa,
        )

        resposta = _pergunta_da_mesa()
    _MESA_SUJA = (agora, resposta)
    return resposta


#: O CENSO DO BARRAMENTO, lido UMA vez e renovado pelo "Examinar Portas" — a
#: mesma regra do `_mesa_do_radio` acima, e pelo mesmo motivo: é varredura de
#: `/sys`, e o tique desta aba é de 100 ms.
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


#: O KERNEL E A LISTA DELA FALAM LÍNGUAS DIFERENTES — e ela decidiu o que fazer
#: com isso em 03/09/2026, perguntada se a "Câmera" do kernel e a "Webcam" da
#: lista dela são a mesma coisa:
#:
#:     "Depende do aparelho. Nem toda 'Câmera' do kernel é a webcam que você
#:      quer marcar. A tela pode SUGERIR e deixar você confirmar, em vez de
#:      decidir sozinha."
#:
#: Então esta tabela NÃO é uma tradução, e a diferença é o ponto inteiro: o que
#: ela produz vira uma PERGUNTA na tela (`— Webcam? —`), nunca uma resposta.
#: Nada chega ao `maquina.json` enquanto ela não tocar.
#:
#: SÓ AS EQUIVALÊNCIAS QUE UMA PESSOA FARIA SEM PENSAR entram aqui. As palavras
#: que o kernel dá e que não têm par na lista dela — "Rede", "Impressora",
#: "Armazenamento", "Não identificado" — não viram sugestão nenhuma: a linha
#: continua em "— O que é? —", que é a verdade. Sugerir "Wi-Fi" a partir da
#: classe `02` (Rede) seria chutar entre o dongle Wi-Fi e o adaptador Ethernet,
#: e é exatamente o número plausível e falso que esta aba não escreve.
#:
#: "Teclado" e "Mouse" NÃO ESTÃO AQUI de propósito: o kernel os nomeia com a
#: MESMA palavra da lista dela (`censo_do_barramento._especie`, pela tripla
#: `03/01/01` e `03/01/02`), e o casamento exato é feito contra
#: `_tipos_de_radio()` — o dono da lista — em vez de repetido nesta tabela.
_SUGESTAO_DO_KERNEL: dict[str, str] = {
    "Câmera": "Webcam",
    "Áudio": "Caixa de som",
}


def _lido_do_kernel(no: str) -> str:
    """A palavra do KERNEL para este nó do sysfs — `""` quando ele não disse.

    PERGUNTA AO DONO e não digita: quem classifica é
    `integrations/censo_do_barramento`, pela tripla `bInterfaceClass /
    SubClass / Protocol`, e `GRAU_LIDO` é a declaração dele de que a palavra
    veio do kernel e não de um chute. Grau `desconhecido` — a classe `ff`, em
    que o fabricante declinou de classificar — devolve `""`, e é aí que a
    pergunta continua sendo a única resposta honesta. É o mesmo degrau que a
    janela estável já consultava (`secao_mesa._celula_do_que_e`).
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations.censo_do_barramento import GRAU_LIDO
    except Exception:
        return ""
    censo = _censo()
    aparelho = censo.aparelho(no) if censo is not None and no else None
    if aparelho is None or getattr(aparelho, "grau", "") != GRAU_LIDO:
        return ""
    return str(getattr(aparelho, "especie", "") or "")


def _sugestao_do_vizinho(no: str, rotulos: Any) -> str:
    """A palavra da LISTA DELA que o kernel sugere para este rádio, ou `""`.

    `rotulos` é o `{rótulo: id}` de :func:`_tipos_de_radio` — o dono da lista.
    Uma sugestão fora dela seria pior que nenhuma: o `<select>` só aceita o que
    OFERECE (`hefesto_vivo.escrever`, alvo `valor`, o teste `o.text === t`), e
    o pintor descartaria a escrita **calado**.
    """
    lido = _lido_do_kernel(no)
    if not lido:
        return ""
    if lido in rotulos:
        return lido
    equivale = _SUGESTAO_DO_KERNEL.get(lido, "")
    return equivale if equivale in rotulos else ""


def _moldura_da_pergunta(pergunta: str) -> tuple[str, str]:
    """O «— … —» da pergunta, LIDO dela e não digitado.

    `"— O que é? —"` devolve `("— ", "? —")`. Se a pergunta um dia perder a
    moldura, a sugestão a perde junto — em vez de ficar com uma moldura que a
    tela não usa mais, que é a régua que digita e envelhece na primeira melhora.
    """
    inicio = 0
    while inicio < len(pergunta) and not pergunta[inicio].isalnum():
        inicio += 1
    fim = len(pergunta)
    while fim > inicio and not pergunta[fim - 1].isalnum():
        fim -= 1
    return pergunta[:inicio], pergunta[fim:]


def _pergunta_sugerida(palavra: str, pergunta: str) -> str:
    """`"— Teclado? —"` — a sugestão vestida de PERGUNTA, nunca de resposta.

    É a marca visível de que aquilo não é resposta dela: a mesma moldura e o
    mesmo ponto de interrogação da pergunta que já estava ali. Ela confirma
    escolhendo "Teclado" na mesma caixa, e só então o `maquina.json` recebe.
    """
    abre, fecha = _moldura_da_pergunta(pergunta)
    return f"{abre}{palavra}{fecha}"


def _perguntas_sugeridas() -> frozenset[str]:
    """Toda pergunta que esta tela pode fazer com uma sugestão dentro.

    PERGUNTA AOS DOIS DONOS — a lista de rótulos é `_TIPOS_DE_RADIO` e a
    moldura é a própria pergunta —, e por isso não envelhece no dia em que a
    lista ganhar uma opção. Digitá-las aqui faria o clique na sugestão nova cair
    no `raise ValueError` do gesto, que nesta aba é recusa **calada**
    (`hefesto_vivo._recusou_dizendo` só leva `RuntimeError` à tela).
    """
    pergunta = _a_pergunta()
    para_id, _ = _tipos_de_radio()
    return frozenset(_pergunta_sugerida(r, pergunta) for r in para_id)


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


#: O ID DO "NÃO SEI" NO DESENHO, e ele é o do produto: o `SegmentedSelector` da
#: janela estável tem `("nao_sei", "Não sei")` nas duas perguntas
#: (`secao_mesa.py:602` e `:618`), e é ele que o `set_active_id` acende.
#:
#: POR QUE ELE NÃO É O `data-modo` DO BOTÃO, e a diferença tem razão medida: o
#: `data-modo` é o que o GESTO manda ao daemon, e ali `""` é o que vira `None`
#: no `machine_declare` — a string `"nao_sei"` faria o pydantic recusar o
#: documento INTEIRO (ver :func:`sala_altura`). Já o `data-hef-quando` é o que o
#: `escrever()` do piloto COMPARA, e ali `""` quer dizer outra coisa: alvo
#: booleano, sem grupo (`hefesto_vivo.py:229`). Um botão marcado com `""` acende
#: por "o valor é verdadeiro", não por "o valor é este" — e os três da fileira
#: acenderiam juntos. São dois vocabulários, e os dois são do produto.
_ID_NAO_SEI = "nao_sei"


def _sala_na_tela(declaracao: Any) -> dict[str, str]:
    """O que ela JÁ RESPONDEU sobre a sala, na língua do `data-hef-quando`.

    **A GTK MOSTRA ISSO DESDE SEMPRE** — `secao_mesa._linha_declarada:671` lê
    `_mesa_em_vigor()` e pré-seleciona o botão gravado ANTES de ligar o sinal.
    Esta tela não mostrava, e o sintoma foi medido nesta bancada em 03/09/2026:
    o `maquina.json` dela diz `altura_da_antena='acima'` e
    `linha_de_visada='com_gente'`, e na página os TRÊS botões da VISADA estavam
    apagados — a tela dizendo que ela não respondeu uma pergunta que ela
    respondeu. O "Sim" da ALTURA estava aceso por coincidência do mockup, que é
    pior: um acerto que não vem de leitura nenhuma erra no primeiro clique dela.

    E ELA CLICA DE NOVO, que é o custo real: sem eco, o segundo clique parece o
    primeiro, e um gesto que grava sem dizer que gravou é indistinguível de um
    gesto que não fez nada.

    O `None` NÃO ACENDE NADA, e a regra é do dono: `secao_mesa:672` só chama
    `set_active_id` quando `gravado is not None`. E tem de ser assim porque o
    produto **não distingue** "nunca respondeu" de "respondeu Não sei" — as duas
    gravam `None` (`sala_altura`: `escolha or None`;
    `secao_mesa._valor_do_seletor:1498` faz a mesma conversão). Acender o "Não
    sei" no `None` poria na boca dela uma resposta que ela pode não ter dado;
    deixar os três apagados é o que as duas telas fazem hoje.

    Por isso :data:`_ID_NAO_SEI` existe no DESENHO e nunca é emitido aqui: ele é
    o que tira o terceiro botão do modo booleano do `escrever()`, e nada mais.
    """
    mesa = _mesa_declarada(declaracao)
    fora: dict[str, str] = {}
    for campo, chave in (("sala-altura", "altura_da_antena"),
                         ("sala-visada", "linha_de_visada")):
        if chave not in mesa:
            continue
        valor = mesa.get(chave)
        fora[campo] = "" if valor is None else str(valor)
    return fora


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


def _pedir_o_exame_de_entrada() -> None:
    """O exame COMPLETO uma vez, ao entrar na aba — como a janela estável faz.

    **A GTK JÁ FAZIA ISSO**, e é o degrau que faltava aqui: `app.py:1180` chama
    `_refresh_saude_da_mesa` ao trocar para a aba Configurações, e
    `secao_exame.reexaminar` corre as CINCO conferências mais as ordens numa
    thread. Ao entrar na aba, lá as cinco linhas estão desenhadas.

    AQUI ELAS NÃO ESTAVAM, e o sintoma foi fotografado nesta bancada em
    03/09/2026: o `_conferencias()` do tique devolve TRÊS itens e o desenho tem
    CINCO blocos `data-campo="exame"`. O piloto distribui a lista por ordem e
    escreve `''` no que sobra (`hefesto_vivo.py:407`), então **duas das cinco
    linhas do Check-up nasciam vazias** — com o ⊘ e o `?` ainda desenhados ao
    lado de um travessão. E a coluna da direita, sem ordem nenhuma para pintar,
    continuava mostrando a ordem de serviço do MOCKUP: *"Mova o adaptador
    Bluetooth da Entrada 3 para a Entrada 9"* — uma instrução para ela mexer no
    gabinete, cravada no arquivo, sobre uma máquina que ninguém examinou.

    UMA VEZ SÓ, E EM THREAD. O exame forka `busctl` com teto de 5 s; correr isso
    no tique de 100 ms seria a janela pedindo ao sistema dez vezes por segundo
    o que ele acabou de responder. `_EXAME_PEDIDO` não se re-arma nem quando o
    exame FALHA — quem rearma é o botão **Examinar Portas**, que é gesto dela.

    A THREAD É `daemon=True` porque ela não guarda nada que precise sobreviver
    ao fechamento da janela: o resultado vive em `_EXTRAS`, que morre com o
    processo. Uma thread não-daemon aqui seguraria o fechamento por até 5 s
    esperando um `busctl` que não interessa mais a ninguém.

    O `except` LARGO É O CONTRATO DA THREAD: uma exceção aqui não tem quem a
    receba — a thread morre calada e o traceback vai para o `stderr` de ninguém.
    Engolir e deixar `_EXTRAS` vazio devolve a tela ao estado de antes desta
    função (três linhas), que é degradação, não quebra.
    """
    global _EXAME_PEDIDO
    if _EXAME_PEDIDO:
        return
    _EXAME_PEDIDO = True
    import threading

    def correr() -> None:
        with contextlib.suppress(Exception):
            _correr_o_exame_completo()

    threading.Thread(target=correr, name="hefesto-exame-de-entrada",
                     daemon=True).start()


def _calada(item: Any) -> bool:
    """Esta linha é uma ordem que ela mandou calar, **neste arranjo**?

    A COMPARAÇÃO EXIGE ARRANJO, e a guarda não é enfeite — 06/09/2026,
    `ONDA5-08-01`. `Ordem.arranjo` tem `""` por padrão
    (`integrations/ordens_da_mesa.py`), e o desfazer desta sprint GRAVA `""` na
    chave. Sem o `and arranjo`, uma ordem viva sem assinatura casaria com o
    vazio guardado e nasceria calada — a tela apagando um achado que ninguém
    dispensou. É a borda que o `ignorar` já descrevia por escrito desde 04/09,
    virada do avesso: o que lá era defeito é aqui o mecanismo, e por isso
    precisa da guarda ao lado.

    **A MESMA GUARDA FALTA EM `integrations/ordens_da_mesa.py`**, em
    `ordens_novas` e `ordens_caladas`, que comparam sem exigir arranjo. Aquele
    arquivo tem outro dono e a janela estável também o lê: está RELATADO, não
    consertado.
    """
    return _ordem_calada(getattr(item, "ordem", None))


def _ordem_calada(ordem: Any) -> bool:
    """A mesma pergunta, feita sobre a ORDEM — é o que o gesto `ignorar` tem na mão.

    UMA COMPARAÇÃO SÓ PARA OS DOIS LADOS. O ⊘ precisa saber se está calando ou
    desfazendo, e a tira precisa saber se pinta em cinza; escrever a comparação
    duas vezes é como o botão passa a desfazer o que a tela mostra como falando
    no dia em que uma das duas mudar.
    """
    if ordem is None:
        return False
    arranjo = str(getattr(ordem, "arranjo", "") or "")
    return bool(arranjo) and _DISPENSADAS.get(str(ordem.chave)) == arranjo


def _itens_da_tela() -> list[Any]:
    """As linhas do Check-up: as três do tique mais o que o exame completo trouxe.

    **A ORDEM CALADA FICA NA TIRA — 08-Q5, 06/09/2026.** Até 05/09 esta função
    DESCARTAVA o que ela tinha dispensado, e a linha sumia da tela: uma porta de
    mão única sobre um clique dela, sem caminho de volta em lugar nenhum desta
    aba. A decisão dela é o contrário — *"A recomendação calada continua no
    lugar dela, em cinza, e o mesmo botão desfaz"* —, e quem diz qual linha está
    calada é :func:`_calada`, lido pela tela em `data-campo="exame-calada"`.

    O QUE NÃO MUDA, e são as duas metades que o filtro segurava sozinho:

    * **a aba Jogar não recebe a calada** — quem filtra é :func:`_exame`, que é
      o contrato daquela aba. Sem aquele passo, calar um alarme aqui o deixaria
      aceso na coluna **Atenção** de lá;
    * **o veredito do topo continua contando só os falantes**
      (:func:`_veredito_do_exame`), senão uma ordem dispensada prenderia o topo
      em laranja para sempre e o ⊘ voltaria a ser botão morto.

    A ORDENAÇÃO DE BAIXO NÃO MUDA: `sorted` é estável e as ordens continuam
    vindo antes das conferências, calada ou não. Mandar a calada para o fim
    seria a mesma tela que esconde, com outro nome.
    """
    conferidas = _conferencias()
    vistas = {getattr(i, "chave", "") for i in conferidas}
    for item in _EXTRAS:
        if getattr(item, "chave", "") in vistas:
            continue
        conferidas.append(item)
    # AS ORDENS VÊM ANTES, E A REGRA É DO PRODUTO — 03/09/2026, `MIGRA-08-01`.
    # `secao_exame._desenhar_o_que_fazer` a escreve com estas palavras: *"As
    # ordens vêm antes das curas de conferência: uma ordem sabe de onde veio
    # cada frase dela, e uma cura de conferência não. O que afirma mais vem
    # primeiro."*
    #
    # AQUI ELA DECIDE O QUE ELA VÊ, e não só a ordem: o desenho tem CINCO blocos
    # de exame, e o exame completo desta máquina devolve SETE itens — as cinco
    # conferências mais duas ordens. Sem esta linha, as duas que sobram são
    # justamente as DUAS ÚNICAS que acusam (`dongle_atras_de_hub` e
    # `teclado_so_no_hub`, ambas `atencao`, medidas nesta  # (noqa-acento) id
    # bancada em 03/09), e a
    # tira fica com cinco CERTO — a tela dizendo "está tudo bem" com dois
    # achados abertos escondidos no fim da lista.
    #
    # O `+N` EXISTE DESDE 06/09/2026 (`exame-mais`, decisão 08-Q7): o que não
    # cabe nos cinco blocos passa a ser DITO. Esta ordenação continua sendo o
    # que garante que o que sobra seja sempre o mais barato de perder — e as
    # duas juntas são o que separa uma tela que não mostra de uma que ESCONDE.
    #
    # `sorted` É ESTÁVEL, então dentro de cada grupo a ordem de chegada fica —
    # as conferências continuam saindo na ordem em que `_conferencias` as roda,
    # que é a ordem dos cinco rótulos da janela estável.
    return sorted(conferidas, key=lambda i: getattr(i, "ordem", None) is None)


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


#: OS ENDEREÇOS DO VEREDITO, um por estado — **S-09, decisão D-16 dela**,
#: 04/09/2026: *"Uma linha de veredito no topo."*, *"Na cor do pior achado."*
#:
#: A GRAMÁTICA É A MESMA DAS CINCO LINHAS (:data:`ENDERECO_DO_ESTADO`), e é de
#: propósito: o alvo `classe` do piloto acende UMA classe por elemento, então um
#: elemento só não tem como escolher entre quatro cores. Aqui não há uma pílula
#: com classe cravada a reaproveitar — a linha nasce do produto —, então os
#: QUATRO são interruptores, inclusive o `problema`.
#:
#: A QUARTA COR JÁ ESTÁ PUBLICADA, e isto é correção de fato: a D-16 diz que ela
#: *"entra junto"* e espera o `--publicar` da 08. Contado na página que ela usa
#: em 04/09/2026: os cinco `selo-estado`, os cinco `selo-certo`, `selo-atencao`
#: e `selo-nao-sei`, e a regra `.selo.grave` do vermelho. Aquela metade da S-09
#: fechou em 03/09; o que faltava era a LINHA.
ENDERECO_DO_VEREDITO = {
    "certo": "veredito-certo",
    "atencao": "veredito-atencao",  # (noqa-acento) chave de máquina, ASCII por contrato
    "problema": "veredito-problema",
    "nao_sei": "veredito-nao-sei",
}


def _veredito_do_exame(vivos: list[Any]) -> dict[str, Any]:
    """A resposta em UMA linha: *"está tudo certo?"* — e a cor do pior achado.

    **D-16, e ela fecha a queixa que a janela estável já não tinha:** o topo do
    Check-up só dizia QUANDO foi examinado. Para saber se há algo errado era
    preciso ler as cinco pílulas e achar a pior — e a segunda ordem de serviço
    desta bancada, que não cabe nas cinco, não entrava nessa leitura de jeito
    nenhum.

    **NENHUMA FRASE NASCE AQUI, E NENHUMA CONTA TAMBÉM.** As quatro frases são
    de `ordens_da_mesa.cabecalho()`, que é o dono declarado — *"a chave de
    estado vem CALCULADA AQUI, num lugar só: um segundo lugar decidindo a cor do
    topo é exatamente como o verde volta a conviver com o vermelho (cicatriz de
    6c86e295)"*. As duas contagens saem de `secao_exame.contagens_do_cabecalho`,
    que as mantém SEPARADAS de propósito: *"conferi 5 coisas"* e *"5 coisas não
    deram resposta"* são afirmações opostas, e a tela que as colapsa mente de
    verde.

    **DUAS PERGUNTAS RESPONDEM SOBRE ESTA LINHA E NENHUMA VÊ A OUTRA**, e é
    `secao_exame.o_mais_grave` quem as concilia: `exame_da_mesa.veredito()` lê
    as linhas conferidas e conhece `problema`; `cabecalho()` lê as ordens e as
    contagens e **não** conhece. Escalar não inventa estado — o resultado é
    sempre um dos dois que entraram —, e o empate devolve o do cabeçalho, que é
    o que tem a frase.

    **O QUE ELA CALOU NÃO SEGURA A COR.** É a mesma regra do
    `_escrever_o_cabecalho` da janela estável: o veredito conta os itens que ela
    NÃO dispensou, senão uma ordem dispensada prenderia o topo em laranja para
    sempre e o ⊘ não faria nada visível — que é a definição de botão morto.

    Devolve o dicionário pronto para o :func:`pacote`: a frase em `veredito` e
    um interruptor por estado. Dicionário VAZIO quando o produto não pôde
    responder — e ele é diferente de uma frase vazia, que o `escrever()` do
    piloto traduziria em travessão: uma linha de juízo dizendo `—` é a tela
    afirmando um nada.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_exame import (
            contagens_do_cabecalho,
            o_mais_grave,
        )
        from hefesto_dualsense4unix.integrations.exame_da_mesa import veredito
        from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
            cabecalho,
            ordens_caladas,
            ordens_novas,
        )
    except Exception:
        return {}
    todas = [o for i in vivos if (o := getattr(i, "ordem", None)) is not None]
    novas = ordens_novas(todas, _DISPENSADAS)
    caladas = ordens_caladas(todas, _DISPENSADAS)
    conferidas, sem_resposta = contagens_do_cabecalho(vivos)
    topo = cabecalho(
        ordens=novas,
        conferidas=conferidas,
        sem_resposta=sem_resposta,
        dispensadas=len(caladas),
    )
    mudas = {o.chave for o in caladas}
    falantes = [
        i for i in vivos
        if (o := getattr(i, "ordem", None)) is None or o.chave not in mudas
    ]
    estado = o_mais_grave(veredito(falantes), topo.estado)
    # A FRASE SÓ VALE COM O ESTADO DELA. Quando o veredito das linhas é MAIS
    # grave que o do cabeçalho, dizer "Nada a mudar" em vermelho seria a
    # contradição exata da cicatriz — e a janela estável resolve trocando a
    # frase pela do estado (`FRASE_DO_SELO`). Aqui a tela não tem esse mapa, e
    # inventá-lo seria a quinta grafia: o que sobra é o texto do dono, e ele só
    # é escrito quando o estado é o dele.
    frase = topo.texto if estado == topo.estado else _frase_do_selo(estado)
    if not frase:
        return {}
    return {
        "veredito": frase,
        **{
            endereco: (estado if estado == qual else "")
            for qual, endereco in ENDERECO_DO_VEREDITO.items()
        },
    }


def _frase_do_selo(estado: str) -> str:
    """A frase do selo quando o estado das LINHAS venceu o do cabeçalho.

    O DONO É `secao_exame.FRASE_DO_SELO`, o mesmo mapa que a janela estável
    escreve nesse caso exato. Import tardio pela razão de sempre neste arquivo.
    """
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_exame import FRASE_DO_SELO

        return str(FRASE_DO_SELO.get(estado, ""))
    return ""


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

    UMA ORDEM DA MESA NÃO TEM VERBETE, E TINHA DE TER O DELA — 02/09/2026, e
    este era o achado de pé desta aba: *"o `?` de uma linha sem verbete e sem
    cura abre uma caixa VAZIA de 330px"*.

    A CAUSA, e ela é do dia anterior: `DICAS_DAS_LINHAS` é indexada por chave de
    REGRA, e são cinco (`energia_do_radio`, `energia_das_portas`, `pareamentos`,
    `suporte_ao_controle`, `vizinhanca_das_portas`). Um item vindo do catálogo
    de ORDENS traz `chave=ordem.chave` — o slug do arranjo, que não é nenhuma
    delas — e `cura=ordem.acao or None`, que pode ser vazio. Sem verbete e sem
    cura, `partes` ficava só com `""` e o `?` abria mostrando o travessão. A
    decisão 9 dela (*"o `?` para de repetir a linha"*) tirou a metade do meio, e
    quem não tinha as outras duas ficou sem nada.

    A CURA É REUSO, e as frases já existiam: uma `Ordem` traz TRÊS linhas
    (`ordens_da_mesa.Ordem.linhas`) com os rótulos de
    `exame_da_mesa.ROTULOS_DA_ORDEM` — *"O que eu vi aqui"*, *"Por que importa"*
    e *"Ganho esperado"*. **A primeira é a que a linha já mostra** (é o
    `Item.porque`), então ela fica de fora e a decisão 9 continua valendo; as
    outras duas são exatamente o que o `?` promete. É o mesmo par que o card do
    GTK escreve (`secao_exame._linha_da_ordem`) e que o `--exame` imprime no
    terminal (`exame_da_mesa._imprimir_relatorio`); esta tela era a única das
    três que as jogava fora.

    O `<b>` DO RÓTULO É O MESMO DA JANELA ESTÁVEL, e por isso ele é composto
    DEPOIS do escape: o rótulo e o texto passam por `_e` separadamente, e a
    marcação entra fora deles. Escapar a frase já montada mostraria `<b>` na
    tela.

    O SELO DE PROCEDÊNCIA (`Linha.selo`) NÃO VEM, e a ausência é da mesma
    natureza da `fonte` em `secao_exame._linha_da_ordem`: ali ele cabe porque o
    card tem uma linha inteira por frase; aqui as duas frases dividem uma dica
    de 330px, e um `[medido]` em cinza no fim de cada uma competiria com o texto
    que ela foi ler. Fica escrito para quem desenhar a dica maior.

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
        from hefesto_dualsense4unix.integrations.exame_da_mesa import (
            ROTULOS_DA_ORDEM,
        )
        from hefesto_dualsense4unix.utils.i18n import _

        # O `_()` É O MESMO DO DONO (`secao_exame` importa este). Sem ele, as
        # duas dicas da mesma linha sairiam por caminhos de tradução
        # diferentes na hora em que esta casa tiver um segundo idioma.
        #
        # CADA PARTE É `(rótulo, texto)`, e o rótulo vazio quer dizer "frase
        # solta". Só as linhas da ordem são rotuladas — o verbete e a cura já
        # trazem o próprio começo.
        partes: list[tuple[str, str]] = [
            ("", _(str(DICAS_DAS_LINHAS.get(str(getattr(item, "chave", "")), ""))))]
        ordem = getattr(item, "ordem", None)
        if ordem is not None:
            # AS DUAS ÚLTIMAS DAS TRÊS. A primeira (`O que eu vi aqui`) é o
            # `Item.porque`, que a linha já mostra — repeti-la aqui desfaria a
            # decisão 9 dela.
            for rotulo, linha in zip(ROTULOS_DA_ORDEM[1:], ordem.linhas[1:],
                                     strict=True):
                partes.append((_(str(rotulo)),
                               _(str(getattr(linha, "texto", "") or ""))))
        cura = str(getattr(item, "cura", "") or "")
        if cura:
            partes.append(("", _(PREFIXO_DA_CURA) + _(cura)))
        return "<br><br>".join(
            (f"<b>{_e(r)}:</b> {_e(t)}" if r else _e(t))
            for r, t in partes if t)
    except Exception:
        return ""


#: A CLASSE DA MARCA DE PROCEDÊNCIA. Ela é uma só nas duas casas onde a marca
#: aparece — o `?` do card e a linha do ganho —, e a folha de estilo desta aba
#: (`aba08.py`) é quem a pinta de cinza.
#:
#: **NA PÁGINA PUBLICADA ELA AINDA NÃO TEM COR**, e isso é declarado e não
#: esquecido: a regra `.proc` nasceu na BANCADA nesta leva e o produto só a
#: recebe no `--publicar`. Até lá a marca sai na cor do texto — legível, e
#: dizendo a mesma coisa. O que NÃO se pode fazer é segurar a marca esperando a
#: folha: a informação é o que ela decide, e a cor é como ela é servida.
_CLASSE_DA_PROCEDENCIA = "proc"


def _marca_da_procedencia(linha: Any) -> str:
    """`[derivado da conta]` — e VAZIO quando a frase foi medida aqui.

    **DECISÃO [04] DO PO, 04/09/2026:** *"Só nas frases que NÃO foram medidas
    aqui. A marca aparece exatamente quando ela muda a decisão dela, e some
    quando não muda."*

    A JANELA ESTÁVEL IMPRIME AS TRÊS (`secao_exame._linha_da_ordem`), e a
    diferença não é descuido: lá a marca mora numa `Gtk.Label` que ocupa a
    largura do card; aqui ela divide um balão de 330 px com duas frases. Três
    marcas seriam o dobro de cinza a atravessar para chegar ao texto.

    **NENHUMA PALAVRA NASCE AQUI.** As três saem de
    `ordens_da_mesa.TEXTO_DO_SELO`, que é o dono — o mesmo mapa que a janela
    estável lê. Um selo que este mapa não conhece sai CRU, e de propósito: uma
    procedência nova tem de aparecer na tela como coisa estranha, não sumir.

    `fonte` NÃO ENTRA, pela razão que `secao_exame._linha_da_ordem` já mediu:
    ela é um caminho desta árvore (`docs/protocol/…`), e quem usa o produto não
    tem esta árvore.
    """
    selo = str(getattr(linha, "selo", "") or "")
    if not selo:
        return ""
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui.aba_conexoes import _e
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        MEDIDO_AQUI,
        TEXTO_DO_SELO,
    )
    from hefesto_dualsense4unix.utils.i18n import _

    if selo == MEDIDO_AQUI:
        return ""
    palavra = str(TEXTO_DO_SELO.get(selo, selo))
    return (f' <span class="{_CLASSE_DA_PROCEDENCIA}">'
            f"[{_e(_(palavra))}]</span>")


def _dica_da_ordem(ordem: Any) -> str:
    """O `?` do card da ordem: *O que eu vi aqui* e *Por que importa*.

    AS DUAS FRASES SÃO DA ORDEM, e os rótulos são de
    `exame_da_mesa.ROTULOS_DA_ORDEM` — os MESMOS que o card do GTK escreve
    (`secao_exame._card_da_ordem:715`) e os mesmos que o `?` de cada linha desta
    tela já usa (:func:`_dica_da_linha`). Nenhuma palavra nasce aqui.

    A TERCEIRA FICA DE FORA porque o card já a mostra por extenso, na linha
    `Ganho esperado:` que `html_da_ordem` emite. Repeti-la no `?` seria a mesma
    frase duas vezes no mesmo cartão — a decisão 9 dela, aplicada ao card.

    **O SELO DE PROCEDÊNCIA ENTROU — 04/09/2026, decisão [04] do PO:** *"Só nas
    frases que NÃO foram medidas aqui."* O que estava escrito neste lugar dizia
    que ele *"continua fora … um `[medido]` em cinza no fim de cada uma
    competiria com o texto que ela foi ler"* — e a medição que sustentava a
    frase continua certa: são DUAS frases num balão de 330 px. O que mudou é a
    regra: `medido aqui` fica IMPLÍCITO e não é escrito, então o balão só ganha
    tinta quando a frase é conta ou vem de terceiro — que é exatamente quando a
    marca muda a decisão dela. Ver :func:`_marca_da_procedencia`.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui.aba_conexoes import _e
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ROTULOS_DA_ORDEM
    from hefesto_dualsense4unix.utils.i18n import _

    partes = [
        f"<b>{_e(_(str(rotulo)))}:</b> "
        f"{_e(_(str(getattr(linha, 'texto', '') or '')))}"
        f"{_marca_da_procedencia(linha)}"
        for rotulo, linha in zip(ROTULOS_DA_ORDEM[:2], ordem.linhas[:2], strict=True)
        if getattr(linha, "texto", "")]
    if not partes:
        return ""
    # O `style` É O DO DESENHO, e não um enfeite: esta dica mora na coluna da
    # DIREITA, e sem ele a caixa de 330px nasce para fora da janela. É o mesmo
    # `left:auto;right:22px` que o gerador crava no `?` deste card.
    return ('<span class="ajuda">?<span class="dica" style="left:auto;right:22px">'
            + "<br><br>".join(partes) + "</span></span>")


def _ordem_na_tela() -> Any:
    """A ordem de serviço que a coluna da direita mostra, ou `None`.

    UMA, E É A PRIMEIRA. O desenho tem UM card, e `ordens_da_mesa` pode devolver
    várias — a GTK desenha um card por ordem numa zona que cresce
    (`secao_exame._desenhar_o_que_fazer`), e aqui não há para onde crescer.
    Mostrar a primeira da tira é o que o `_ORDENS_NA_TELA` já endereça: é a
    mesma ordem que o ⊘ da linha dela dispensa.

    O QUE SOBRA NÃO É MENTIRA, MAS ESCONDE, e é o mesmo buraco que
    `gui.aba_conexoes.sobraram` mede na janela estável. Fica escrito para quem
    desenhar o "+N" desta coluna.
    """
    return next((o for o in _ORDENS_NA_TELA if o is not None), None)


def _dono_sabe_desenhar_a_ordem() -> bool:
    """O `gui.aba_conexoes.html_da_ordem` já aguenta uma `Ordem` de verdade?

    **HOJE NÃO, E O DEFEITO É DELE** — medido nesta bancada em 03/09/2026, com
    as DUAS ordens abertas na máquina dela (`dongle_atras_de_hub` e
    `teclado_so_no_hub`)::

        AttributeError: 'Identidade' object has no attribute 'onde'
        gui/aba_conexoes.py:733   {_e(ordem.alvo.onde or TRACO)}

    `ordens_da_mesa.Identidade` tem `vid`, `pid`, `caminho` e `ambigua` — e
    nunca teve `onde`. A função **jamais correu com uma ordem**: o único
    chamador era `aba_conexoes.pintura:935`, e `pintura(ordem=None)` é o padrão,
    então todas as chamadas caíam no ramo do `None`, que funciona. É a forma de
    defeito que esta casa chama de *ramo morto por construção* — e ela só
    apareceu quando alguém foi usar a função para o que ela existe.

    ESTA FUNÇÃO É A CATRACA. `gui/aba_conexoes.py` é de outro dono, e enquanto
    ele não fechar, :func:`_card_da_ordem` desenha aqui. No dia em que fechar,
    esta função devolve `True`, o teste
    `test_o_dono_ainda_nao_desenha_a_ordem_da_mesa_08` fica VERMELHO, e quem o
    ler apaga a segunda grafia e volta a chamar o dono. Uma duplicação que sabe
    a data da própria morte é o preço aceitável; uma que não sabe é dívida.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui import aba_conexoes as _tela
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        DERIVADO_DA_CONTA,
        Linha,
        Ordem,
    )

    frase = Linha(texto="x", selo=DERIVADO_DA_CONTA)
    prova = Ordem(chave="prova", acao="x", o_que_eu_vi=frase,
                  por_que_importa=frase, ganho_esperado=frase)
    try:
        _tela.html_da_ordem(prova)
    except AttributeError:
        return False
    return True


def _card_da_ordem(ordem: Any) -> str:
    """O card de UMA ordem: o imperativo, o `?`, o de→para e o ganho.

    SEGUNDA GRAFIA COM DATA DE MORTE — ver :func:`_dono_sabe_desenhar_a_ordem`.
    As classes são as do desenho dela (`.ordem`, `.faca`, `.receita`, `.caixa`,
    `.seta`, `.ganho`), as mesmas que o dono emite; o que muda é que aqui a
    `Ordem` é lida pelos campos que ela TEM.

    A RECEITA SÓ APARECE COM DESTINO, e é o que o dono não faz: ele emite as
    duas caixas sempre, e com `destino` vazio a tela mostraria `—  →  —`. Nas
    DUAS ordens desta máquina o `destino` é `''` — a regra achou o problema e
    não achou entrada livre nomeável para onde mandar (`SEM_DESTINO`). Um
    de→para de travessão para travessão é ruído com cara de diagnóstico.

    O QUE VAI NA CAIXA DA ESQUERDA é o `alvo.caminho` — o endereço de barramento
    (`3-1.2`), que é *"a palavra comum entre este módulo, o censo e o mapa"*
    (`gui.aba_conexoes.html_dos_adaptadores`). A "Entrada 3" do desenho é o
    número do MAPA DELA, e só existe depois que ela desenhar as entradas — o que
    a própria `acao` desta ordem diz com todas as letras.  (noqa-acento: campo)

    O GANHO VAI SEMPRE, inclusive quando ele confessa que não foi medido: *"AS
    TRÊS, SEMPRE — inclusive a que confessa que o ganho não foi medido"*
    (`secao_exame._card_da_ordem`). Esconder a terceira linha custaria uma linha
    de tela e a confiança inteira.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui.aba_conexoes import TRACO, _e
    from hefesto_dualsense4unix.utils.i18n import _

    partes = [f'<div class="faca">{_e(_(str(ordem.acao)))}{_dica_da_ordem(ordem)}</div>']
    destino = str(getattr(ordem, "destino", "") or "")
    if destino:
        de = str(getattr(getattr(ordem, "alvo", None), "caminho", "") or TRACO)
        partes.append(
            f'<div class="receita"><span class="caixa">{_e(de)}</span>'
            f'<span class="seta">→</span>'
            f'<span class="caixa alvo">{_e(destino)}</span></div>')
    ganho = str(getattr(ordem.ganho_esperado, "texto", "") or "")
    if ganho:
        # O RÓTULO É O TERCEIRO DE `ROTULOS_DA_ORDEM` — "Ganho esperado" —, o
        # mesmo que o card do GTK e o `--exame` do terminal escrevem. Ele está
        # digitado no desenho desta aba, e digitá-lo aqui de novo seria a
        # terceira grafia da mesma palavra.
        from hefesto_dualsense4unix.integrations.exame_da_mesa import ROTULOS_DA_ORDEM

        # E A MARCA DE PROCEDÊNCIA VAI AQUI TAMBÉM — decisão [04]. Nesta mesa a
        # terceira linha é `DERIVADO_DA_CONTA` nas duas ordens abertas, então a
        # marca aparece: é o card confessando que o ganho foi CALCULADO e não
        # medido, no mesmo lugar em que ele o promete.
        partes.append(
            f'<div class="ganho"><span>{_e(_(str(ROTULOS_DA_ORDEM[2])))}:</span> '
            f"{_e(_(ganho))}{_marca_da_procedencia(ordem.ganho_esperado)}</div>")
    return f'<div class="ordem">{"".join(partes)}</div>'


#: O PREFIXO DA CURA e o teto de cards da coluna. Os dois têm dono no produto:
#: a palavra é `secao_exame.PREFIXO_DA_CURA` (lida no ato, nunca copiada), e o
#: teto é o do DESENHO — a coluna da direita tem UM card de ordem, e quatro
#: cards de cura é a altura da coluna do exame ao lado.
#:
#: QUATRO É O QUE A MÁQUINA PODE RENDER: são cinco conferências e uma delas
#: (`energia_das_portas`) não escreve cura. A janela estável não tem teto porque
#: a zona dela cresce; aqui a seção divide altura com as outras duas do quadro.
_TETO_DE_CURAS = 4

#: OS OUTROS DOIS TETOS DO DESENHO — decisão **08-Q7**, 06/09/2026. Eles moram
#: aqui, ao lado do primeiro, porque o `+N` é conta do PRODUTO e o número é do
#: DESENHO: a coluna do exame tem CINCO blocos e a fileira dos vizinhos QUATRO.
#:
#: **LIDOS DE UM LUGAR SÓ, nunca digitados nos dois arquivos.** O `aba08.py`
#: importa este pacote (`_pacote08`) e emite os blocos por estes mesmos números;
#: um teto digitado no gerador e outro no pacote divergiria no dia em que a
#: coluna crescesse, e o `+N` passaria a contar o que cabe em vez do que sobra.
TETO_DO_EXAME = 5
TETO_DE_VIZINHOS = 4


def _monta() -> Any:
    """O módulo `interface/monta.py`, importável de dentro do pacote.

    ELE PRECISA DE UM APELIDO, e não é capricho: `monta.py` faz `import onde`
    CRU — nasceu como script de gerador, e naquele contexto a pasta `interface/`
    é o `sys.path[0]`. Importado como módulo de pacote ele levanta
    `ModuleNotFoundError: No module named 'onde'`, medido em 03/09/2026.

    O APELIDO É EM `sys.modules`, NUNCA UM `sys.path.insert`, pela razão que
    `a09_sistema._monta` escreve: pôr a pasta `interface/` no caminho de busca
    deixaria `casamento`, `mapa`, `regua`, `ver` e mais vinte nomes curtos
    visíveis como módulos de topo para todo o processo.

    **É A SEGUNDA CÓPIA DESTE HELPER, e ela é declarada** — a primeira é
    `a09_sistema._monta`. Promovê-lo a `pacotes/__init__.py` é mudança em
    arquivo de outra posse (`ONDA4-S10` está nele nesta leva); fica RELATADO.
    """
    import sys

    from hefesto_dualsense4unix.interface import onde as _onde

    sys.modules.setdefault("onde", _onde)
    from hefesto_dualsense4unix.interface import monta

    return monta


def _card_da_cura(item: Any) -> str:
    """O card de uma conferência que tem CURA e não tem ordem — decisão [03].

    **DECISÃO [03] DO PO, 04/09/2026:** *"Cartão de cura na coluna da direita."*
    Até hoje a cura das conferências só existia dentro do `?` de cada linha
    (:func:`_dica_da_linha`), e quem não passasse o mouse não descobria o que
    fazer. A janela estável esteve nesse mesmo estado e saiu dele em 25/08 —
    `secao_exame._card_da_cura`, cuja nota diz por quê com todas as letras: *"a
    cura de quatro das cinco conferências chegava à tela SÓ dentro de um
    tooltip"*.

    **SEM SELO DE PROCEDÊNCIA, e é regra do dono, não economia:** *"uma cura de
    conferência não traz selo … porque não há medição por trás dela dizendo de
    onde vem o conselho. Pôr um selo aqui seria dar ao raciocínio a roupa da
    medição, que é o que o selo existe para impedir."* É a contramão exata da
    decisão [04], e as duas convivem porque falam de coisas diferentes: a ORDEM
    sabe de onde veio cada frase; a cura de conferência, não.

    A CLASSE É `ordem cura`, e o primeiro nome não é enfeite: `.ordem` é a única
    moldura que a página PUBLICADA já sabe desenhar. Enquanto a folha da bancada
    não for publicada, o card de cura nasce com a moldura do card de ordem — que
    é o parecido certo, e não um bloco solto sem borda.

    A PÍLULA É A MESMA DA LINHA DO EXAME — a palavra e a classe saem de
    `gui.aba_conexoes.SELO_DO_ESTADO`, o dono do mapa. O card fala do MESMO
    achado que a linha da esquerda, e duas gramáticas para o mesmo estado é como
    o verde volta a conviver com o vermelho. **Ela não é o selo de procedência**,
    que é o que o parágrafo acima recusa: uma diz o ESTADO do achado, a outra
    diria de onde veio a frase.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_exame import PREFIXO_DA_CURA
    from hefesto_dualsense4unix.gui.aba_conexoes import _e
    from hefesto_dualsense4unix.utils.i18n import _

    classe, palavra = _selo_do_estado(str(getattr(item, "estado", "") or ""))
    cura = str(getattr(item, "cura", "") or "")
    porque = str(getattr(item, "porque", "") or "")
    # O TEXTO VAI DENTRO DE UM `<span>`, e não solto: `.ordem .faca` é `display:
    # flex` com `gap:8px`, então cada filho inline vira um ITEM da flexbox — um
    # `<b>` no meio da frase abriria oito pixels de vão de cada lado dele.
    # Medido na foto de 04/09, antes desta linha existir.
    corpo = [f'<div class="faca"><span class="selo {classe}">{_e(_(palavra))}</span>'
             f"<span>{_e(_(str(PREFIXO_DA_CURA)) + _(cura))}</span></div>"]
    if porque:
        corpo.append(f'<div class="ganho"><span></span>{_e(_(porque))}</div>')
    return f'<div class="ordem cura">{"".join(corpo)}</div>'


#: A FRASE DO `+N`, e ela tem UM dono nesta casa — este.
#:
#: **PROCUREI O DONO ANTES DE ESCREVER, e ele não existe.** A dívida do "+N"
#: está escrita em quatro lugares desta árvore apontando para
#: `gui.aba_conexoes.sobraram` como se ele fosse a frase; medido em 04/09/2026,
#: `sobraram(controles)` devolve um **int** e fala do ACORDEÃO, não do exame.
#: Chamá-lo aqui teria posto na tela a conta de outra lista — a armadilha que
#: esta casa chama de *perguntar no lugar errado*.
#:
#: O MOLDE É O DA DECISÃO [07] DO PO, ao pé da letra: *"+1 recomendação não
#: coube aqui"*. O substantivo é de quem chama, porque as três listas desta aba
#: contam coisas diferentes; a moldura é uma só, para as três dizerem o mesmo
#: fato do mesmo jeito.
_MAIS_N = "+{n} {coisa} não {coube} aqui"


def _sobraram(quantos: int, cabem: int, um: str, muitos: str) -> str:
    """A linha `+N` do fim de uma lista — decisão [07]. VAZIA quando cabe tudo.

    **DECISÃO [07] DO PO, 04/09/2026:** *"Um '+N' no fim de cada lista. É a
    diferença entre uma tela que não mostra e uma tela que ESCONDE — e só custa
    linha no dia em que sobra."*

    O QUE ELA CURA ESTÁ MEDIDO, e estava escrito como dívida em três lugares
    deste arquivo: o exame de 03/09 devolveu DUAS ordens abertas, a coluna da
    direita tem UM card, *"e a segunda não aparece em lugar nenhum"*.

    **SÓ CUSTA LINHA NO DIA EM QUE SOBRA** — com tudo cabendo, devolve `""` e a
    coluna fica exatamente como estava. É a mesma gramática da D-02 (a ressalva
    que não ocupa nada em repouso), e é o que a torna barata.
    """
    if quantos <= cabem:
        return ""
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui.aba_conexoes import _e
    from hefesto_dualsense4unix.utils.i18n import _

    n = quantos - cabem
    frase = _(_MAIS_N).format(
        n=n, coisa=(um if n == 1 else muitos),
        coube=("coube" if n == 1 else "couberam"))
    return f'<div class="mais">{_e(frase)}</div>'


def _o_que_nao_coube(itens: list[Any], vizinhos: list[Any]) -> dict[str, str]:
    """Os DOIS `+N` que faltavam nesta aba — decisão **08-Q7** dela, 06/09/2026.

    *"Quando sobra, a lista ganha uma última linha curta: '+1 recomendação não
    coube aqui' — e só no dia em que sobra."* A trava que ela leu: *"hoje a sua
    bancada já perde uma recomendação em silêncio"* — o exame desta máquina
    devolve SETE itens e a coluna tem CINCO blocos.

    **CADA UM CONTA A PRÓPRIA LISTA, e as duas chegam juntas por isso:** o
    `+N` do exame conta os itens da tira e o dos vizinhos conta os rádios. É a
    régua do erro que esta aba já cometeu — `gui.aba_conexoes.sobraram` está
    citado em quatro lugares desta árvore como se fosse o dono desta frase, e
    ele devolve um `int` sobre o ACORDEÃO. Perguntar no lugar errado produz
    não-achado convincente.

    **O `monta.NADA_A_DIZER` NO LUGAR DO VAZIO, e ele é obrigatório:** o
    `escrever()` do piloto troca valor vazio por `—` ANTES de olhar o alvo, e um
    `""` daqui poria um travessão solto sob a quinta linha do exame TODO DIA.
    `.ressalva:has(.nada){display:none}` é a peça que faz a linha só existir no
    dia em que sobra — é para isso que ela existe.

    **AS DUAS CHAVES VÃO EM TODO TIQUE**, inclusive quando cabe tudo: omiti-las
    deixaria na tela o `+N` do tique anterior depois de ela desligar um rádio.
    """
    nada = _monta().NADA_A_DIZER
    return {
        "exame-mais": _sobraram(len(itens), TETO_DO_EXAME,
                                "achado", "achados") or nada,
        "vizinho-mais": _sobraram(len(vizinhos), TETO_DE_VIZINHOS,
                                  "rádio vizinho", "rádios vizinhos") or nada,
    }


def _html_da_ordem(vivos: list[Any] | None = None) -> str:
    """A coluna da direita inteira: a ordem, as curas e o que não coube.

    TRÊS DECISÕES DO PO MORAM NESTA FUNÇÃO, e é de propósito que elas moram
    juntas: a coluna é UM endereço (`data-campo="ordem"`, alvo `html`), e quem
    decide o que cabe nela tem de ver as três listas ao mesmo tempo.

    * **[03]** o cartão de cura, abaixo da ordem — :func:`_card_da_cura`;
    * **[04]** o selo de procedência nas frases não medidas aqui;
    * **[07]** o `+N` quando há mais ordem aberta do que card.

    A ORDEM DOS CARDS É A DO PRODUTO, e a razão está escrita em
    `secao_exame._desenhar_o_que_fazer`: *"As ordens vêm antes das curas de
    conferência: uma ordem sabe de onde veio cada frase dela, e uma cura de
    conferência não. O que afirma mais vem primeiro."*

    `vivos` É A MESMA LISTA QUE PINTOU A TIRA, e recebê-la é o que impede as duas
    metades da seção de discordarem: se esta função relesse o exame, a coluna da
    direita poderia falar de um achado que a coluna da esquerda não mostra. Sem
    ela — o padrão — só o card da ordem sai, que é o que esta função fazia antes.

    ---

    O QUE ESTAVA NA TELA DELA NO LUGAR, fotografado nesta bancada em 03/09/2026:
    um card cravado no arquivo mandando **mover o adaptador Bluetooth da Entrada
    3 para a Entrada 9**, com de→para, ganho e um `?` de duas frases — tudo
    escrito à mão no mockup, tudo apresentado como diagnóstico da máquina dela.
    É a forma mais cara de mentira que uma tela sabe cometer: não um número
    errado, mas uma INSTRUÇÃO para mexer no gabinete.

    O QUE A MÁQUINA DELA DIZ DE VERDADE, medido no mesmo dia: DUAS ordens
    abertas, e nenhuma delas fala de Entrada 3 nem de Entrada 9 —
    `dongle_atras_de_hub` (*"2 de 3 adaptadores Bluetooth chegam ao computador
    por dentro de um hub"*) e `teclado_so_no_hub` (*"Se o hub sair da tomada,
    você fica sem teclado antes de o Linux abrir."*).

    `None` TEM TEXTO PRÓPRIO, E ELE É DO DONO: *"Nenhuma mudança recomendada
    agora."* (`gui.aba_conexoes.html_da_ordem`, o ramo que funciona). Ele só é
    honesto porque o exame COMPLETO corre ao entrar na aba
    (:func:`_pedir_o_exame_de_entrada`) — sem aquilo, este cartão diria "nada a
    fazer" sobre uma máquina que ninguém tinha examinado, que é a mesma
    ausência-lida-como-sucesso com outra roupa.

    COM ORDEM, QUEM DESENHA É :func:`_card_da_ordem`, e a razão é um defeito do
    dono, não uma escolha: ver :func:`_dono_sabe_desenhar_a_ordem`.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui import aba_conexoes as _tela
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_CERTO

    ordem = _ordem_na_tela()
    partes = [_tela.html_da_ordem(None) if ordem is None else _card_da_ordem(ordem)]
    if vivos is None:
        return partes[0]
    # AS ORDENS ABERTAS QUE NÃO COUBERAM — decisão [07]. `_ordem_na_tela` mostra
    # a PRIMEIRA e o desenho tem UM card; nesta mesa o exame de 03/09 devolveu
    # DUAS, e a segunda não aparecia em lugar nenhum.
    abertas = sum(1 for i in vivos if getattr(i, "ordem", None) is not None)
    partes.append(_sobraram(abertas, 1, "recomendação", "recomendações"))
    # AS CURAS DAS CONFERÊNCIAS — decisão [03]. A REGRA DOS TRÊS FILTROS É DO
    # DONO (`secao_exame._desenhar_o_que_fazer`), lida linha a linha: sem ordem
    # (a ordem já tem card), COM cura (não há o que dizer sem ela) e o estado
    # diferente de CERTO — uma conferência que passou não pede conserto.
    curas = [i for i in vivos
             if getattr(i, "ordem", None) is None
             and str(getattr(i, "cura", "") or "")
             and str(getattr(i, "estado", "")) != ESTADO_CERTO]
    partes += [_card_da_cura(i) for i in curas[:_TETO_DE_CURAS]]
    partes.append(_sobraram(len(curas), _TETO_DE_CURAS, "cura", "curas"))
    return "".join(p for p in partes if p)


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
        # para exatamente isto: `classe` (`hefesto_vivo.py:499`, com
        # `data-hef-classe` e `data-hef-quando`) e `cor` (`:537`). O que a
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
        # A LINHA ESTÁ CALADA? — 08-Q5, 06/09/2026. `"sim"` é o valor que o
        # `data-hef-quando` do desenho espera; o VAZIO é o outro estado, e ele
        # tem de ser emitido também: a chave que só aparece quando há o que
        # dizer deixa na tela a tinta do tique anterior, e a linha que voltou
        # ficaria cinza para sempre.
        "calada": "sim" if _calada(item) else "",
        # O `title` DO ⊘, e ele muda de VERBO com o estado — porque o botão
        # muda de sentido. Ver :data:`DICA_DO_IGNORAR` e :data:`DICA_DO_DESFAZER`.
        "dica-do-ignorar": DICA_DO_DESFAZER if _calada(item) else DICA_DO_IGNORAR,
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

    **A CALADA NÃO ATRAVESSA ESTE CONTRATO — 06/09/2026, `ONDA5-08-01`.** Desde
    a 08-Q5 a ordem dispensada FICA na tira desta aba, em cinza; a filtragem
    mudou de lugar e passou a ser daqui. Sem este filtro, calar um alarme na
    Conexões o deixaria aceso na coluna **Atenção** da Jogar — a mesma
    contradição de duas telas que o `_do_exame` de lá existe para não ter, e um
    alarme que ela já respondeu.

    **É AQUI E NÃO EM `_itens_da_tela` PORQUE A CURA COBRE TODOS OS CHAMADORES**
    sem tocar em arquivo de outra posse: a pintura desta aba não passa por esta
    função (o :func:`pacote` chama `_itens_da_tela()` direto), então a 08
    continua vendo tudo e a 01 continua vendo só o que fala. É a regra que esta
    casa pagou duas vezes em 05/09 — cobrir um chamador deixa a próxima pessoa
    remedindo o mesmo defeito.
    """
    return [_linha(i) for i in _itens_da_tela() if not _calada(i)]


def _adaptadores(conectados: Any, state: Any = None) -> dict[str, Any]:
    """Quem está em qual adaptador de rádio.

    O MAC NÃO SAI DAQUI CRU para lugar nenhum que se grave: este pacote devolve
    para a tela em memória, e a máscara da casa (octetos 4 e 5 zerados) é o que
    vai para qualquer relato. São dois portões nesta árvore e eles não perdoam.

    ESTA PONTE NUNCA PASSOU TRÁFEGO — consertado em 05/09/2026
    ---------------------------------------------------------
    Até hoje a chamada era ``ocupacao_por_adaptador([c.get("uniq") for c in
    conectados])`` — uma lista de **strings**. O dono
    (`integrations/radio_da_mesa.py:323`) declara `Iterable[Mapping]` e faz
    ``controle.get("transport")``, então a chamada levantava
    ``AttributeError: 'str' object has no attribute 'get'`` **sempre**, e o
    ``except Exception`` abaixo engolia.

    Medido em 05/09/2026 com o python desta árvore::

        ocupacao_por_adaptador(['aabbcc000011'])          -> AttributeError
        ocupacao_por_adaptador([{'uniq': …, 'transport': 'bt'}])
            -> {'': Ocupacao(slots_input=260.4, …)}

    Resultado: a chave ``adaptadores`` deste pacote era **sempre ``{}``**, em
    toda máquina, desde que a linha foi escrita. O sintoma era a AUSÊNCIA de
    dado, que não quebra tela nenhuma — a assinatura de defeito mais cara desta
    casa. E é por isso que `html_da_regua_do_radio` recalcula a ocupação por
    conta própria em 353 linhas, em vez de ler o dono.

    A SEGUNDA METADE: `com_ponte_de_mic`. A GTK passa o conjunto
    (`app/actions/config/secao_mesa.py:1335`), e sem ele a conta ignora o custo
    do microfone no rádio — 260,4 onde a GTK conta 276,7 para um controle com a
    ponte de pé. A fonte é ``state["bt_mic"]["uniqs"]``, e a ausência da chave
    vira conjunto vazio pela mesma razão escrita lá: um daemon mais velho que a
    janela não a manda, e cair seria pior que contar sem o microfone.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations import radio_da_mesa

        bloco = (state or {}).get("bt_mic") if isinstance(state, dict) else None
        uniqs = bloco.get("uniqs") if isinstance(bloco, dict) else None
        com_mic = (
            frozenset(u for u in uniqs if isinstance(u, str))
            if isinstance(uniqs, list)
            else frozenset()
        )

        ocup = radio_da_mesa.ocupacao_por_adaptador(conectados, com_ponte_de_mic=com_mic)
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


#: A CONTA DA CONFISSÃO POR EXTENSO. **ESTE DICIONÁRIO É O DONO DOS DOIS
#: LADOS** — o gerador o importa daqui, e por isso a palavra da bancada e a
#: palavra da mesa dela não podem divergir.
#:
#: É dado DERIVADO (`len(lacunas)`), não frase de tela: a abertura, os itens e a
#: ordem continuam saindo de `mapa_da_mesa.CONFISSAO`, que é o dono do texto.
PALAVRA_DA_CONTA = {0: "nada", 1: "uma coisa", 2: "duas coisas", 3: "três coisas",
                    4: "quatro coisas", 5: "cinco coisas"}


def palavra_da_conta(quantas: int) -> str:
    """`3` → "três coisas". Fora da tabela, o número cru — nunca uma palavra errada.

    A RESERVA NÃO É DESLEIXO: a cena pode acender uma sexta lacuna no dia em que
    `mapa_da_mesa.CONFISSAO` crescer, e escrever "cinco coisas" sobre seis seria
    a tela afirmando uma contagem que ela não fez. O gerador tem um `raise` para
    o mesmo caso — ele PARA a geração; aqui, no tique de 100 ms da mesa dela,
    parar não é opção e o número por extenso vira número.
    """
    return PALAVRA_DA_CONTA.get(int(quantas), str(int(quantas)))


def _confissao_do_mapa() -> dict[str, str]:
    """Os campos da confissão — o que o desenho DELA não consegue conferir.

    O DONO DAS FRASES É `mapa_da_mesa.confissao_do_desenho`, o mesmo que a
    janela do desenho redesenha a cada mudança. Aqui elas só ganham a moldura do
    HTML: a conta por extenso na linha e os itens no `title`.

    O DEFEITO QUE ISTO FECHA, medido nesta bancada em 03/09/2026: a
    `.mm-conf-linha` está FORA do bloco `.mm-faces` que o pacote troca, então
    ninguém nunca a repintava. Ela dizia **"três coisas"** — a conta da cena do
    mockup — e o `title` listava as três; a mesa dela tem **UMA** lacuna
    (`especie`). Uma confissão que confessa a mais é tão falsa quanto uma que
    cala: manda ela procurar duas coisas que o produto já sabe.

    `confissao-nada` É O INTERRUPTOR DO SUMIÇO, e a regra é da GTK: lá a linha
    SOME quando o desenho responde por tudo (`confissao_do_desenho` devolve
    vazio e o `_desenhar` não escreve nada). Sem ele, zero lacuna viraria *"O
    que eu não consegui conferir neste desenho: nada."* — uma frase que ocupa
    espaço para não dizer nada.

    O DICIONÁRIO VAZIO É RESPOSTA, e é por isso que esta função não devolve
    tupla: sem censo o pacote não sabe quantas lacunas há, e emitir `""` seria
    PIOR que não emitir — o `escrever()` do piloto troca vazio por travessão, e
    a tela diria *"O que eu não consegui conferir neste desenho: —."*. Não
    emitir deixa a linha como o desenho a escreveu, que é o único estado
    honesto quando a leitura do barramento falhou.
    """
    bancada = _bancada()
    if bancada is None:
        return {}
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import (
            confissao_do_desenho,
        )

        itens = tuple(confissao_do_desenho(bancada))
    except Exception:
        return {}
    if not itens:
        # A LINHA SOME, e a conta vai junto: se a folha de estilo desta página
        # ainda não tiver a regra do `sumido`, o que ela lê é "nada" — que é
        # verdade — em vez de um travessão.
        return {"confissao-nada": "sim", "confissao-conta": palavra_da_conta(0)}
    # O `\n` DE VERDADE, e não o `&#10;` do gerador: aquele é uma entidade HTML,
    # e o gerador a escreve porque o texto dele entra CRU dentro de `title="…"`
    # no arquivo. Aqui o valor viaja como JSON e o piloto o põe por
    # `setAttribute`, onde entidade nenhuma é interpretada — um `&#10;` chegaria
    # à dica dela escrito com todas as letras.
    abertura = _abertura_da_confissao()
    return {"confissao-nada": "",
            "confissao-conta": palavra_da_conta(len(itens)),
            "confissao-dica": "\n".join([abertura, *(f"· {t}" for t in itens)])}


def _abertura_da_confissao() -> str:
    """*"O que eu não consegui conferir neste desenho:"* — a frase do produto.

    Ela é de `mapa_da_mesa.CONFISSAO_ABERTURA`, a mesma constante que a janela
    do desenho escreve em cima da lista e que o gerador lê para o `title` do
    mockup. Digitá-la aqui seria a segunda grafia da abertura, e a primeira
    coisa que uma segunda grafia perde é a revisão dela.
    """
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import (
            CONFISSAO_ABERTURA,
        )

        return str(CONFISSAO_ABERTURA)
    return ""


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


def _html_dos_externos(ctx: Contexto) -> str:
    """Uma linha por controle que o Hefesto VÊ e NÃO adota — ``""`` sem nenhum.

    **A LINHA 305 DO CSV DA PARIDADE**, e a acusação dela é curta: *"uma aba
    chamada Conexões que não lista metade dos controles conectados"*. O `porque`
    daquela linha era um grep — *"por `controller.list` em `interface/pacotes/`
    não acha uma chamada"* —, e desde esta sprint acha: quem pergunta é o piloto,
    no tique lento (`hefesto_vivo._talvez_ler_os_externos`), e a resposta chega
    aqui por `ctx.externos`, que é campo PRÓPRIO do contexto.

    **O CONTEÚDO É O MESMO DA ABA 01, E ISSO É DELIBERADO.** As três frases têm
    UM dono cada (`_format_external_title`, `_format_external_subtitle`,
    `external_controllers.nintendo_bt_warning`), e é por elas passarem pelo mesmo
    dono que as duas abas não podem discordar sobre o mesmo aparelho — que é o
    defeito que esta casa nomeia *"a tela afirmando o que não é"*, visto quatro
    vezes num dia só de 31/08.

    **O AVISO DO `hid-nintendo` É O SINAL DESTA LINHA DO CSV**, e ele não acusa o
    Hefesto nem promete cura: a morte é do driver do kernel com firmware clone
    em modo Switch, e a saída estável é o cabo. O dono da frase mediu isso
    (`nintendo_bt_warning`), e ela nasce só quando as duas condições valem — VID
    Nintendo E rádio. Nos outros aparelhos a linha não existe.

    **A LISTA MORA DENTRO DA MOLDURA `.gc` — escolha DELA, 06/09/2026.** A
    EXTERNOS-01 a pôs numa ressalva embaixo do acordeão e PERGUNTOU: à parte, ou
    no mesmo frame, como a janela GTK fazia? A resposta foi o mesmo frame. Quem
    faz a linha virar item da moldura é o CSS da bancada (`aba08.py`,
    `.gc .ext-vaga{display:contents}`); este pacote continua devolvendo só as
    linhas, e não sabe onde elas caem.

    **MAS ELA NÃO VIRA UM `.gc-item`, e a razão da EXTERNOS-01 não caducou:**
    cada `.gc-item` tem `data-controle="pN"`, um rádio de alvo de saída e um
    corpo que se abre. Um externo não tem assento, não é alvo de saída de nada e
    não tem o que abrir — pô-lo ali daria à tela um sexto rádio apontando para
    um aparelho em que o daemon não escreve. **Estar na mesma moldura é uma
    escolha de DESENHO; ser um assento é uma afirmação sobre o aparelho**, e
    esta função não faz a segunda.

    **QUEM A DISTINGUE É A MARCA**, e é o que a janela GTK fazia: o assento diz
    o nome do controle, o externo diz *"Controle 4 — Nintendo"*. A palavra vem
    de ``external_controllers.brand_of`` por dentro de
    ``_format_external_title``; nenhuma marca se digita aqui.
    """
    if not ctx.externos:
        return ""
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        nintendo_bt_warning,
    )
    from hefesto_dualsense4unix.app.actions.home_actions import (
        _format_external_subtitle,
        _format_external_title,
    )
    def _e(x: object) -> str:
        """Escapa para HTML — pelo `html.escape` da biblioteca, e não pelo `_e`
        da janela GTK.

        `gui.aba_conexoes._e` é exatamente esta linha, e importá-lo seria uma
        citação NOVA para uma janela que está saindo (`D-0609-GTK-LEVA-INTEIRA`):
        o portão `nada-aponta-para-a-janela` reprovou a primeira volta desta
        sprint por isso, e a regra é que aquela lista só diminui. **O que se
        reusa da janela é o MOTOR** — as frases, que vêm de `app/actions/` —,
        nunca a janela. É a mesma escolha que `a09_sistema.py` já faz.
        """
        return html.escape(str(x), quote=True)

    fora = []
    for entrada in ctx.externos:
        aviso = nintendo_bt_warning(entrada)
        linha_do_aviso = (f'<span class="ext-aviso">{_e(aviso)}</span>'
                          if aviso else "")
        # AS TRÊS COLUNAS SÃO AS DO `.gc-cabeca`, e não um arranjo novo: o nome
        # numa coluna de largura fixa (`--larg-nome`, o mesmo número das quatro
        # linhas de cima), o resto esticando. O `_PONTO` que separava o nome do
        # transporte SAIU com ele — dentro da moldura quem separa as colunas é o
        # vão, como já separa nas linhas dos assentos, e um bullet no meio de
        # uma coluna alinhada lê como um item de lista solto.
        fora.append(
            '<div class="ext-linha">'
            f'<span class="ext-nome">{_e(_format_external_title(entrada))}</span>'
            f'<span class="ext-via">{_e(_format_external_subtitle(entrada))}</span>'
            f'{linha_do_aviso}</div>')
    return "".join(fora)


#: A PALAVRA DA COLUNA "Nome" QUANDO ELA NÃO DEU NOME, e ela tem UM dono: é a
#: mesma que `gui.aba_conexoes.html_dos_adaptadores` escreve. O gerador a lia da
#: própria cópia até 04/09/2026 — duas grafias da mesma célula, e a tabela
#: passou a ser pintada por este arquivo, que é onde a terceira nasceria.
SEM_NOME = "Sem nome"

#: A DICA DO CAMPO DE NOME. **DUAS ESCRITAS, UM DONO** — mesma razão de
#: :func:`rotulo_do_controle`: o gerador a escreve no mockup e este pacote a
#: escreve a cada tique, e enquanto ela morou só no `aba08.py` a tabela viva não
#: tinha de onde tirá-la.
#:
#: O RENOMEAR DEIXOU DE SER BOTÃO — 31/08/2026, decisão dela: *"tirar o botão
#: Renomear e adicionar a possibilidade de renomear dando duplo clique no
#: nome"*. `contenteditable` é o que o mockup sabe fazer sem uma linha de
#: JavaScript; o DUPLO clique é gesto do produto, e é ele que a dica promete.
RENOMEAR_DICA = (
    "Dê um duplo clique para dar um nome seu a este adaptador — “Sala”, "
    "“Extra”. É por ele que o resto da tela passa a chamá-lo."
)

#: O cabeçalho da tabela dos adaptadores. Ele viaja JUNTO com as linhas porque o
#: bloco inteiro é trocado por `innerHTML` — o mesmo molde do `.mm-faces` e da
#: régua do rádio. Deixá-lo fora obrigaria a pintura a conhecer a estrutura do
#: `<table>` do desenho, que é o acoplamento que o alvo `html` existe para
#: evitar.
_CABECALHO_DOS_ADAPTADORES = (
    "<tr><th>Nome</th><th>Adaptador</th><th>Onde está</th></tr>"
)

#: O que a tabela diz quando a varredura do barramento não respondeu. Ela é
#: DIFERENTE de "nenhum adaptador": ausência de leitura não é ausência de
#: aparelho, e é o defeito que esta casa chama de *ausência de notícia lida
#: como sucesso*. O `None` de `_mesa_do_radio` é o único caminho até aqui.
_NAO_CONSEGUI_LER_OS_ADAPTADORES = "Não consegui ler os adaptadores agora."

#: E o que ela diz quando LEU e não havia nenhum. A frase é a da janela estável
#: (`secao_mesa`), e existe porque uma tabela vazia lê como tela quebrada.
_NENHUM_ADAPTADOR = "Nenhum adaptador Bluetooth encontrado."


def _apelidos_por_interface() -> dict[str, str]:
    """`{hciN: o nome que ELA deu}` — vazio quando o BlueZ não respondeu.

    O DONO DA COSTURA É `apelido_do_dongle.Dongle.nome`, que devolve o alias
    **sem** a marca que o produto acrescenta. Ler `alias` cru aqui poria na
    coluna o nome com a costura, que é o que a janela estável evita de
    propósito (`secao_mesa._campo_do_nome`).
    """
    dongles = _dongles()
    if not dongles:
        return {}
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
            _dongle_por_interface,
        )

        return {
            interface: nome
            for interface, dongle in _dongle_por_interface(dongles).items()
            if (nome := str(getattr(dongle, "nome", "") or ""))
        }
    return {}


def _html_dos_adaptadores() -> str:
    """A tabela "Nome · Adaptador · Onde está" com os adaptadores DELA.

    ELA ERA CENÁRIO — e é a tabela mais lida desta aba. O desenho crava duas
    linhas ("Sala / TP-Link UB500 / Entrada 3 · traseira" e "Sem nome / Intel
    AX211 / Interno · M.2") sobre uma bancada que tem **TRÊS** adaptadores, os
    três `2357:0604`. Medido em 04/09/2026: `ler_a_mesa()` devolve três, e o
    BlueZ dá a cada um o nome que ela escreveu.

    AS TRÊS COLUNAS TÊM TRÊS DONOS, e nenhuma frase nasce aqui:

    * **Nome** — `apelido_do_dongle.Dongle.nome`, o alias dela sem a costura;
    * **Adaptador** — `secao_mesa._nome_do_adaptador`, que é VID:PID e **nunca**
      `hciN`: o índice inverte entre boots, e um nome que troca de dono faz a
      pessoa mexer na porta errada (decisão M1);
    * **Onde está** — `secao_mesa._onde_esta_o_adaptador`, que já fala o número
      do mapa DELA quando ela desenhou a mesa, e desce a procedência para o
      `title`.

    O `contenteditable` DA PRIMEIRA CÉLULA CONTINUA, porque o gesto de renomear
    é dela e é duplo clique (`RENOMEAR_DICA`, decisão de 31/08). O que muda é o
    texto que ele começa editando: o nome do adaptador, e não "Sala".

    **E A CÉLULA GANHOU DONO — 04/09/2026.** Ela era `contenteditable` e mais
    nada: nenhum gesto, e `apelido_do_dongle` sem um único chamador na interface
    nova. *Ela digitava e perdia.* Agora a célula leva o `data-hef-gesto` e o
    `data-caminho` — o endereço de barramento, que é a palavra comum desta aba —,
    e o gesto :func:`renomear_adaptador` grava no BlueZ.

    **O `hciN` NÃO VAI PARA O HTML** (decisão M1) e o endereço, tampouco: o
    `data-caminho` é `3-1.2`, e quem o traduz em BD Address é
    :func:`_endereco_e_nome_do_adaptador`, no ato do clique.
    """
    mesa = _mesa_do_radio()
    if mesa is None:
        return f'{_CABECALHO_DOS_ADAPTADORES}<tr><td colspan="3" class="mudo">' \
               f"{_NAO_CONSEGUI_LER_OS_ADAPTADORES}</td></tr>"
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
        _nome_do_adaptador,
        _onde_esta_o_adaptador,
    )
    from hefesto_dualsense4unix.gui.aba_conexoes import _e

    apelidos = _apelidos_por_interface()
    mapa = getattr(_declaracao(), "mapa", None)
    linhas = []
    for a in tuple(getattr(mesa, "adaptadores", ()) or ()):
        nome = apelidos.get(str(getattr(a, "interface", "")), "")
        onde, dica = _onde_esta_o_adaptador(a, mapa)
        mudo = "" if nome else ' class="mudo"'
        # A PROCEDÊNCIA SÓ VAI QUANDO EXISTE. `_onde_esta_o_adaptador` devolve
        # `None` de dica para o adaptador que não está em entrada declarada, e
        # pôr a dica do RENOMEAR nessa célula seria prometer, no hover da coluna
        # "Onde está", um gesto que é da coluna "Nome".
        titulo = f' title="{_e(dica)}"' if dica else ""
        linhas.append(
            f"<tr><td{mudo}>"
            f'<span class="renomeia" contenteditable="true" '
            f'data-hef-gesto="{GESTO_DO_APELIDO}" '
            f'data-caminho="{_e(str(getattr(a, "caminho", "") or ""))}" '
            f'title="{_e(RENOMEAR_DICA)}">{_e(nome or SEM_NOME)}</span></td>'
            f'<td class="mudo">{_e(_nome_do_adaptador(a))}</td>'
            f"<td{titulo}>{_e(onde)}</td></tr>")
    if not linhas:
        linhas = [f'<tr><td colspan="3" class="mudo">{_NENHUM_ADAPTADOR}</td></tr>']
    return _CABECALHO_DOS_ADAPTADORES + "".join(linhas)


def _onde_dos_vizinhos(mesa: Any) -> list[str]:
    """A terceira coluna do bloco de cada rádio vizinho: **onde ele está**.

    E ELA CARREGA O AVISO DE VIZINHANÇA, que é o mesmo fato que a linha do
    Check-up chama de *"dois rádios da bancada estão em entradas vizinhas"* —
    só que dito ao lado do rádio CULPADO. Na janela estável ele aparece nos
    dois lugares; aqui aparecia só na linha do exame, sem dizer qual dos rádios
    é. Medido nesta bancada em 04/09/2026: o `3554:fa09` é *"vizinho do
    adaptador 3"*, e os outros dois calam.

    OS DOIS DONOS SÃO DO PRODUTO — `secao_mesa._onde_esta_o_radio` (que já
    junta o painel com o aviso, e já fala o número do mapa dela quando existe) e
    `secao_mesa._avisos_de_vizinhanca` (que garante **um** aviso por par: são
    dois aparelhos e UM problema, e marcar os dois leria como dois).
    """
    if mesa is None:
        return []
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
            _avisos_de_vizinhanca,
            _onde_esta_o_radio,
        )

        avisos = _avisos_de_vizinhanca(mesa)
        mapa = getattr(_declaracao(), "mapa", None)
        return [
            _onde_esta_o_radio(r, avisos.get(str(getattr(r, "no", ""))), mapa)
            for r in tuple(getattr(mesa, "radios", ()) or ())
        ]
    return []


def _dicas_dos_vizinhos(mesa: Any) -> list[str]:
    """O `title` de cada "onde" — a segunda metade do aviso de vizinhança.

    `_avisos_de_vizinhanca` devolve `(sufixo, dica)`: o sufixo entra na coluna
    (é o que se lê sem gesto nenhum) e a dica diz POR QUE aquilo importa. Sem
    ela a coluna acusaria sem explicar, que é a metade que a janela estável
    nunca deixou de fora.
    """
    if mesa is None:
        return []
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
            _avisos_de_vizinhanca,
        )

        avisos = _avisos_de_vizinhanca(mesa)
        return [
            (avisos.get(str(getattr(r, "no", ""))) or ("", ""))[1]
            for r in tuple(getattr(mesa, "radios", ()) or ())
        ]
    return []


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


#: O SEPARADOR DO DESENHO. Ele é um `<span>` com classe, e não um `•` solto,
#: porque a folha dela pinta o ponto mais apagado que o texto em volta. As duas
#: funções que compõem frase para esta tela usam este mesmo — ver
#: :func:`rotulo_do_controle`, que já o escrevia.
_PONTO = ' <span class="pt">•</span> '


def html_da_conta(frase: str) -> str:
    """A frase da contagem, com o separador que o desenho dela usa.

    O DONO DA FRASE É `gui.aba_conexoes.texto_da_contagem` — *"2 na mesa • 1 no
    cabo • 1 no rádio"* —, e ele escreve o `•` cru porque nasceu para um rótulo
    do GTK. Esta função é só a tradução para o HTML dela; nenhuma palavra e
    nenhum número nascem aqui.

    POR QUE O GERADOR TAMBÉM CHAMA ISTO (`aba08.py`): enquanto o desenho e o
    produto escreverem a mesma frase duas vezes, elas divergem sem que ninguém
    veja. É a mesma razão pela qual o gerador já importava
    :func:`rotulo_do_controle` e :func:`tinta_legivel` deste módulo.
    """
    return frase.replace(" • ", _PONTO)


#: POR ONDE O MICROFONE DESTE CONTROLE CHEGA — as duas metades da frase, e elas
#: são as do desenho dela. A regra é o ponto final dela de 28/08: *"se tiver em
#: modo rádio, então o mic é modo rádio"* — não há chavinha, o caminho é
#: DERIVADO do transporte. Pelo CABO o DualSense expõe placa USB Audio própria e
#: o PipeWire a publica sozinho; pelo RÁDIO não existe placa nenhuma e o áudio
#: vem em Opus dentro do HID 0x31, trazido pela ponte do Hefesto.
_CAMINHO_DO_MIC = {"bt": ("pelo rádio", "Pela ponte"),
                   "usb": ("pelo cabo", "Placa do controle")}


def caminho_do_microfone(via: str) -> str:
    """*"pelo rádio • Pela ponte"* ou *"pelo cabo • Placa do controle"*.

    **UM DONO SÓ PARA OS DOIS LADOS**, mesmo molde de :func:`rotulo_do_controle`
    e :func:`html_da_conta`: o gerador chama isto com a mesa da BANCADA, o
    pacote chama a cada tique com o transporte VIVO. Enquanto a frase morava só
    no `aba08.caminho_do_mic`, a linha fechada dizia *"pelo cabo · Placa do
    controle"* no P1 e *"pelo rádio · Pela ponte"* no P2 porque foi assim que o
    desenho os desenhou — não porque o daemon tenha dito.

    O TRANSPORTE DESCONHECIDO CAI NO CABO, e é a escolha conservadora: a ponte
    de rádio é o que CUSTA turno, e afirmá-la sem leitura poria na tela um preço
    que ninguém mediu. O gerador já fazia o mesmo (`via != "BT"` → cabo).
    """
    chave = (via or "").strip().lower()
    rota, quem = _CAMINHO_DO_MIC.get(chave, _CAMINHO_DO_MIC["usb"])
    return f"{rota}{_PONTO}{quem}"


#: A METADE FÍSICA DA DICA DO MICROFONE — a que o desenho já escrevia, e que
#: continua sendo verdade porque é FATO de protocolo, não conclusão de produto.
#: Pelo cabo o DualSense expõe uma placa USB Audio própria (medido em
#: 15/08/2026); pelo rádio não existe placa nenhuma, e o áudio vem em Opus
#: dentro do relatório HID 0x31.
#:
#: **O QUE ELA NÃO DIZ MAIS**, e é a correção de 04/09: nenhuma das duas
#: condiciona a FEATURE ao transporte. O que muda com o transporte é a ROTA — e
#: a rota é consequência, exatamente como a chavinha *"pelo cabo / pelo rádio"*
#: que saiu desta aba porque *"oferecia uma escolha que o transporte já tinha
#: feito"*. A frase do custo entra derivada, logo abaixo.
_DICA_DO_MIC = {
    "bt": (
        "O microfone deste controle chega <b>pelo rádio</b>: o DualSense não tem "
        "A2DP nem HFP, então o áudio vem em Opus dentro do relatório HID e o "
        "Hefesto publica uma fonte de captura do PipeWire com ele."
    ),
    "usb": (
        "O microfone deste controle chega <b>pelo cabo</b>, pela placa de áudio "
        "USB do próprio aparelho — o PipeWire a publica sozinho (medido em "
        "15/08/2026)."
    ),
}

#: O que se diz do custo quando ele não existe. Pelo cabo o microfone não passa
#: pelo rádio, então não há fatia a contar — e dizer "0 turnos" seria um número
#: onde não há conta.
_MIC_NAO_CUSTA_RADIO = "Pelo cabo ele não custa turno de rádio nenhum."


def dica_do_microfone(via: str) -> str:
    """O `title` da linha do microfone: por onde ele chega e quanto ele custa.

    **O NÚMERO DEIXA DE SER DIGITADO — 04/09/2026.** O desenho cravava
    *"Custa +16,3 turnos de rádio"* no `title` do resumo, e os 16,3 conferiam
    com `radio_da_mesa` **hoje**: eles são a segunda grafia, e no dia em que
    alguém remedir o A/B a janela estável acompanha e o HTML não. É exatamente a
    forma de defeito que `frase_da_capacidade_do_mic` foi escrita para impedir —
    ela deriva os quatro números das constantes do medidor, *"que é o mesmo
    lugar de onde a barra de Rádio em uso tira os dela"*.

    A FRASE DO CUSTO SÓ ENTRA NO RÁDIO, e é a mesma regra do medidor: pelo cabo
    o microfone não toca o rádio. O que muda com o transporte é a ROTA e o
    PREÇO — nunca se o microfone existe.
    """
    chave = (via or "").strip().lower()
    fisica = _DICA_DO_MIC.get(chave, _DICA_DO_MIC["usb"])
    if chave != "bt":
        return f"{fisica} {_MIC_NAO_CUSTA_RADIO}"
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_controles import (
            frase_da_capacidade_do_mic,
        )

        return f"{fisica} {frase_da_capacidade_do_mic()}"
    return fisica


#: O VALOR DO `data-hef-quando` DO BOTÃO "A luz não acende" — 03/09/2026.
#:
#: A CURA É DO RÁDIO, e o botão do desenho já nascia apagado no cabo. O que ele
#: não tinha era ENDEREÇO: a classe `apagado` do P1 vinha do mockup, e o P2
#: nascia aceso pela mesma razão. Com um controle só na mesa, e no cabo, a tela
#: dela mostrava um botão ACESO para o lugar vazio e um apagado para o cheio —
#: a decisão de acender vinha da posição no desenho, nunca do transporte.
#:
#: A PALAVRA É A DO GESTO: `luz_nao_acende` recusa quando o transporte não é
#: `bt`, com a frase do cabo. Este campo é a mesma regra um instante ANTES do
#: clique, que é onde a janela estável a põe (`secao_controles.pode_derrubar`).
LUZ_TRAVADA = "cabo"
LUZ_LIVRE = "radio"  # (noqa-acento) valor de atributo, ASCII por contrato


def trava_da_luz(via: str) -> str:
    """`"cabo"` quando o botão da luz não tem o que fazer; `"radio"` quando tem.

    O DONO DA REGRA É O GESTO (:func:`luz_nao_acende`), que levanta com a frase
    do produto para todo transporte que não seja `bt`. Ler a mesma condição aqui
    é o que faz a tela DIZER ANTES o que o gesto diria depois — a metade que a
    GTK tem desde sempre e que o HTML devolvia só como tarja pós-clique.

    TRANSPORTE VAZIO É TRAVA, e pela mesma razão do gesto: `Disconnect` sobre um
    controle cujo transporte ninguém leu é um pedido no escuro.

    O LUGAR VAZIO NÃO É ALCANÇADO POR AQUI, E ISSO É DÍVIDA — medida no DOM vivo
    em 03/09/2026 com um controle só na mesa. As `colunas` só existem para quem
    está conectado; o lugar que sobra recebe `dict.fromkeys(chaves, TRAVESSAO)`
    (`pacotes/__init__.py:323`), e no alvo `classe` o travessão não casa com
    `data-hef-quando` nenhum — logo ele APAGA a classe que o desenho pôs. O
    botão do lugar vazio fica ACESO.

    **NÃO SE CURA INVERTENDO ISTO.** Emitir o travessão como valor de "travado"
    faria a ausência de dado e o cabo dizerem a mesma coisa, que é a confusão
    que esta casa mais pagou. A cura é uma das duas, e nenhuma cabe neste
    arquivo: `classe` entrar em `ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE` (um alvo de
    classe não tem o que fazer com um traço — ele só apaga o que o desenho
    afirmou), ou o desenho dela ganhar o estado do lugar vazio. A tela de HOJE
    já mostrava esse botão aceso pelo mesmo pixel — era a classe do mockup —,
    então não há regressão; o que muda é que agora há um dono a quem cobrar.
    """
    return LUZ_LIVRE if (via or "").strip().lower() == "bt" else LUZ_TRAVADA


def dica_da_luz(via: str, nascimento: Any = None, mesa_suja: bool | None = None) -> str:
    """A dica do botão "A luz não acende" — a do PRODUTO, e nunca vazia.

    **TRÊS COISAS QUE A TELA NÃO DIZIA, e as três têm dono no produto:**

    1. **por que o botão está apagado.** O `title` do desenho é congelado: o
       primeiro cartão diz *"Este controle está no cabo"* e o segundo diz o que
       o clique faz — e os dois continuam dizendo isso quando o controle troca
       de transporte. A cor já obedecia (`trava_da_luz`, 03/09); a frase, não.
       `secao_controles.dica_do_botao` decide as duas juntas, e é ela quem passa
       a escrever;
    2. **o AVISO DA MESA SUJA.** Quando outro programa está segurando nó de
       controle agora, a conexão nova nasce travada igual — e a cura que o botão
       oferece não pega. A janela estável ANEXA o aviso à dica, nunca no lugar:
       a pessoa continua precisando saber o que o botão faz. Aqui não havia
       nada; ela clicava, não funcionava, e não havia segunda frase;
    3. **a RAZÃO de a cura ser oferecida** — `frase_do_nascimento`, o carimbo
       que o daemon põe na conexão (`SINAL-NO-NASCIMENTO-01`). Só a condenação
       fala: ausência, `limpa` e `nao_sei` calam, cada um por um motivo medido
       no dono. O `nascimento` chega por controle no `state_full`
       (`ipc_handlers.py:3632`) e pacote nenhum o lia.

    **NENHUMA FRASE NASCE AQUI.** O que este arquivo faz é a junção — a mesma
    que `secao_controles._card_do_controle` faz do lado da janela estável — e a
    ordem: o que o botão faz primeiro, a razão de ele estar sendo oferecido
    depois. O `▲` da razão já vem do dono.

    `mesa_suja` é `True`/`False`/`None`, e o `None` **não** vira aviso: alarme
    sem medição atrás ensina a ignorar alarme.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        dica_do_botao,
        frase_do_nascimento,
    )

    # `dica_do_botao` pergunta ao objeto três coisas (`adotado`, `no_cabo`,
    # `uniq`), e as três são as MESMAS que `trava_da_luz` já respondeu para a
    # cor. Um objeto anônimo com esses três campos é o que faz as duas metades
    # do botão — a cor e a frase — saírem da mesma pergunta em vez de duas.
    no_radio = trava_da_luz(via) == LUZ_LIVRE
    dados = _dataclasses.make_dataclass(
        "ControleDaLuz", ["adotado", "no_cabo", "uniq"])(True, not no_radio, "x")
    dica = dica_do_botao(dados, mesa_suja=bool(mesa_suja is True))
    razao = frase_do_nascimento(nascimento) if no_radio else None
    return f"{dica} {razao}" if razao else dica


# ---------------------------------------------------------------------------
# A ESPERA PELO PS — a contagem, o Cancelar e o recado que sobrevive
# ---------------------------------------------------------------------------
#
# O DESENHO PROMETIA E O PRODUTO NÃO ENTREGAVA. O `title` do botão diz, com
# todas as letras: *"Enquanto ele espera o PS, o mesmo botão vira 'Cancelar'"*.
# Até 06/09/2026 o gesto derrubava o controle e voltava — sem contagem, sem
# Cancelar e sem recado. Ela clicava, o controle caía, e a tela não dizia uma
# palavra sobre o que fazer nem por quanto tempo esperar.
#
# NADA AQUI É MÁQUINA NOVA. Quem sabe esperar é `secao_controles.EsperaPeloPS`,
# o dono na janela estável: dois marcos (VER SUMIR, e só depois ver voltar), os
# quatro desfechos, e as frases do fim. Ele foi escrito sem GTK, sem IPC e sem
# relógio de propósito — *"quem chama dá o tique"* —, e é exatamente por isso
# que a interface nova pôde reusá-lo inteiro em vez de reescrever a espera.
#
# O QUE ESTE ARQUIVO ACRESCENTA É O RELÓGIO, e ele não pode ser o tique do
# piloto: o tique é de 100 ms (`hefesto_vivo.TIQUE_MS`) e a espera conta
# SEGUNDOS. Chamar `tique()` uma vez por pintura faria os 60 segundos do dono
# virarem seis — a contagem correria dez vezes mais rápido que o relógio dela.
# Por isso o avanço é medido em tempo MONOTÔNICO, e o `EsperaPeloPS` recebe um
# `tique()` por segundo inteiro decorrido, nem mais nem menos.
#
# E O RELÓGIO É MONOTÔNICO PELA MESMA RAZÃO DO CANAL DE RECADO: um acerto de
# hora do sistema no meio da espera não pode fazer a contagem pular nem voltar.

#: As esperas VIVAS, por `uniq` normalizado. Estado de módulo pela mesma razão
#: escrita no cabeçalho deste arquivo: o `Contexto` é remontado a cada tique e
#: não tem onde guardar nada entre um tique e o seguinte. Quem escreve é o gesto
#: (numa thread) e quem lê é a pintura — e as duas operações são atribuições de
#: chave, então nenhuma das duas vê metade de nada.
_ESPERAS: dict[str, _EsperaNaTela] = {}


class _EsperaNaTela:
    """Uma espera pelo PS, com o relógio por fora e o recado por dentro.

    `espera` é o dono (:class:`secao_controles.EsperaPeloPS`); `recado` é a
    frase do fim, que **sobrevive** ao fim da espera de propósito — sem ela
    "não voltou" viraria silêncio, que é o defeito que o ELO-MUDO-01 nomeou.
    """

    def __init__(self, espera: Any, agora: float) -> None:
        self.espera = espera
        #: O instante do último segundo já contado.
        self.desde = float(agora)
        self.recado = ""

    @property
    def contando(self) -> bool:
        return not bool(self.espera.acabou)

    def correr(self, agora: float) -> None:
        """Entrega ao dono um `tique()` por segundo inteiro decorrido."""
        if self.espera.acabou:
            return
        passou = int(float(agora) - self.desde)
        if passou <= 0:
            return
        self.desde += passou
        for _ in range(passou):
            self.espera.tique()
            if self.espera.acabou:
                break
        if self.espera.acabou:
            self.recado = str(self.espera.porque or "")


def _agora() -> float:
    """O relógio da espera. MONOTÔNICO — ver o cabeçalho desta seção."""
    return time.monotonic()


def comecar_a_espera(uniq: str, *, agora: float | None = None,
                     sonda: Any = None) -> Any:
    """O controle caiu do rádio; a tela entra no estado 2 do desenho.

    `sonda` é o ponto de injeção da régua, e ele existe pela mesma razão que no
    dono: a sonda de verdade lê o `/sys` de quem roda o teste, e uma régua que
    dependesse dela mediria a bancada de quem a executa em vez do código.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        EsperaPeloPS,
    )

    dele = _EsperaNaTela(
        EsperaPeloPS(uniq) if sonda is None else EsperaPeloPS(uniq, sonda=sonda),
        _agora() if agora is None else agora)
    _ESPERAS[norm_mac(uniq) or ""] = dele
    return dele


def cancelar_a_espera(uniq: str) -> bool:
    """Ela desistiu. `True` quando havia espera a cancelar.

    **NÃO RECONECTA**, e a regra é do dono: *"o botão PS é dela"*. Cancelar
    devolve o cartão ao estado 1 e mais nada — o controle continua fora do
    rádio, pareado, esperando o PS quando ela quiser.
    """
    dele = _ESPERAS.get(norm_mac(uniq) or "")
    if dele is None or not dele.contando:
        return False
    dele.espera.cancelar()
    dele.recado = ""
    return True


def esperando(uniq: str) -> bool:
    """Este controle está no estado 2 do desenho AGORA?"""
    dele = _ESPERAS.get(norm_mac(uniq) or "")
    return dele is not None and dele.contando


def _correr_as_esperas(presentes: set[str], agora: float | None = None) -> None:
    """Um passo do relógio, UMA vez por tique, para todas as esperas vivas.

    `presentes` são os `uniq` que o daemon está publicando AGORA, e eles servem
    para UMA coisa: **apagar o recado de quem voltou**. "Não voltou em 60s" é
    verdade no instante em que é escrita e vira mentira assim que o controle
    reaparece — e um recado que envelhece na tela é a mesma família do desenho
    que promete o que o produto não faz. Os outros dois desfechos que falam
    (`nao_caiu`) continuam verdadeiros, e ficam até o próximo clique.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        ESPERA_NAO_VOLTOU,
    )

    quando = _agora() if agora is None else agora
    for chave, dele in list(_ESPERAS.items()):
        dele.correr(quando)
        if (not dele.contando and dele.recado and chave in presentes
                and dele.espera.estado == ESPERA_NAO_VOLTOU):
            dele.recado = ""


def texto_do_botao_da_luz(uniq: str = "") -> str:
    """O rótulo do botão: `"A luz não acende"`, ou `"Cancelar"` na espera.

    **As duas palavras são do dono** (`secao_controles.TEXTO_DO_BOTAO` e
    `TEXTO_CANCELAR`), e é essa a metade que faz o `title` do desenho deixar de
    ser promessa: ele já dizia *"o mesmo botão vira 'Cancelar'"*, e agora vira.

    SEM `uniq` DEVOLVE O RÓTULO DE REPOUSO, e é assim que o GERADOR o chama: o
    desenho da bancada não tem espera de ninguém dentro, e a palavra que ele
    escreve tem de ser a MESMA do dono — foi por ela estar digitada no gerador
    que o `title` pôde prometer um estado por dias sem ninguém notar.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        TEXTO_CANCELAR,
        TEXTO_DO_BOTAO,
    )

    return TEXTO_CANCELAR if esperando(uniq) else TEXTO_DO_BOTAO


def linha_da_espera(uniq: str) -> str:
    """A linha de ressalva do cartão: o pedido do PS com a contagem, ou o recado.

    **NENHUMA FRASE NASCE AQUI**, e é a mesma junção que :func:`dica_da_luz`
    faz um pouco acima: `FRASE_APERTE_PS` é o aviso do dono (o mesmo que a
    janela estável mostra como *"▲ aperte PS"*) e `frase_da_procura` é a
    contagem dele, palavra por palavra. O que este arquivo escolhe é a ORDEM e
    o separador — o pedido primeiro, o relógio depois.

    Fora da espera devolve o recado do fim, e sem recado devolve
    :func:`_sem_valor`, que faz a `.ressalva` SUMIR em vez de virar um `—`.
    """
    dele = _ESPERAS.get(norm_mac(uniq) or "")
    if dele is None:
        return _sem_valor()
    if dele.contando:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_controles import (
            FRASE_APERTE_PS,
            frase_da_procura,
        )

        return (f"▲ {html.escape(FRASE_APERTE_PS)} · "
                f"{html.escape(frase_da_procura(dele.espera.restantes))}")
    return html.escape(dele.recado) if dele.recado else _sem_valor()


#: COMO A TELA LÊ O `mic_button_toggles_system` — **D-12, 04/09/2026**, e ela
#: transforma a única escolha desta aba que o produto não sabia guardar numa
#: LEITURA.
#:
#: O QUE ESTAVA AQUI ANTES ERA UM `<select>` MORTO: a tela oferecia *"Só este
#: controle"* ou *"O computador inteiro"* POR CONTROLE, e o produto guarda UM por
#: máquina (`daemon/lifecycle.py:301`, aplicado por `ipc_draft_applier.py:592`).
#: A recusa estava registrada em `SEM_GESTO` e só aparecia no terminal, a cada
#: clique — um botão que não faz nada e não diz nada.
#:
#: **A DOUTRINA É A DESTA MESMA ABA**, e ela já a aplicou uma vez: a chavinha
#: *"pelo cabo / pelo rádio"* SAIU porque *"oferecia uma escolha que o
#: transporte já tinha feito"*, e os 16,3 turnos viraram consequência. Aqui é
#: igual — a escolha já foi feita, e foi por ela: *"o botão do Controle sempre
#: controla a interface"* (30/08) mais *"o botão é pra ligar o microfone e ele
#: ser ouvido no canal específico dele"* (D-12), que é UM ato só. Com esse
#: conceito não há duas rotas com dois comportamentos, e a tela **diz** o que o
#: botão físico faz em vez de perguntá-lo.
#:
#: AS DUAS FRASES SÃO AS DO `<select>` QUE SAIU — nem uma palavra nova. Elas
#: eram o rótulo das duas opções e passam a ser a resposta.
FALA_DO_BOTAO_DO_MIC = {
    True: "O computador inteiro",
    False: "Só este controle",
}


def escopo_do_botao_do_mic(estado: Any) -> str:
    """O que o botão FÍSICO do microfone cala — lido do daemon, um por máquina.

    A chave é `mic_button_toggles_system`, publicada pelo `state_full` desde o
    `MIC-EXPOSE-01` (*"o botão de mic deixa de ser campo secreto do lifecycle —
    a GUI/CLI leem o estado efetivo daqui"*). Medido na máquina dela em
    04/09/2026: `True`.

    AUSÊNCIA DEVOLVE VAZIO, e não o padrão do `DaemonConfig`: um daemon que não
    respondeu não é um daemon que respondeu `True`. O `escrever()` do piloto
    traduz vazio em travessão, que é a resposta honesta.
    """
    valor = (estado or {}).get("mic_button_toggles_system")
    return "" if valor is None else FALA_DO_BOTAO_DO_MIC[bool(valor)]


def _tela_da_aba() -> Any:
    """`gui.aba_conexoes` — a camada de tela desta aba, do lado do produto.

    Um atalho e não um import de topo: este módulo é importado pelo despachante
    antes de o `src/` estar no caminho, e `perfil._com_o_src()` é o que o põe lá
    (mesma razão escrita em `_html_do_mapa` e em `_dica_da_linha`).
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui import aba_conexoes

    return aba_conexoes


def _texto_da_bateria(bruto: Any) -> str:
    """`100%`, ou o travessão do produto quando ninguém leu.

    O DONO É `gui.aba_conexoes.Controle.texto_da_bateria`, e é ele que decide
    que a ausência vira **travessão** e não zero: *"sem fonte, escreve `— %` em
    vez de um número herdado"* é a regra que a janela estável já segue
    (`status_actions._set_battery_text`).

    O `Controle` É CONSTRUÍDO SÓ PARA ISSO, com os outros campos no valor
    neutro, e é de propósito: a alternativa era escrever `f"{n}%"` aqui, que é a
    segunda grafia da mesma regra — e a primeira coisa que se perde numa segunda
    grafia é justamente o caso do `None`.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui.aba_conexoes import Controle

    n = int(bruto) if isinstance(bruto, int | float) else None
    return Controle(uniq="", jogador=0, via="", bateria=n).texto_da_bateria


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

    OITO DOS 28 MODELOS NÃO TÊM HEX, e ignorar isso derrubava a aba INTEIRA —
    achado em 03/09/2026 ao passar os 28 pelo pacote, um a um. Chroma Teal,
    Chroma Indigo, Chroma Pearl, Grey Camouflage, Ghost of Yōtei, Marathon,
    Genshin Impact e 007 First Light são pintados no mapa dela com uma HACHURA
    (`url(#hachura-sem-hex)`), que é como ela escreve *"esta cor eu não medi"*.
    O valor atravessava até `tinta_legivel`, e ali
    `int("ur", 16)` levanta `ValueError` **fora** do `try` deste bloco: quem
    ligasse um Chroma Teal via a `08-conexoes` parar de pintar por completo, sem
    uma barra na tela e sem um erro que dissesse por quê.

    A hachura é uma resposta legítima e vale para o DESENHO — ele a mostra, e é
    a informação certa. O que ela não é é uma COR: não dá para pintar com ela
    uma barra de 3px nem calcular a tinta que se lê por cima. Aqui, então, ela é
    ausência de leitura — a mesma regra dela, pela mesma razão.
    """
    if not slug:
        return ""
    try:
        import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

        cor = str(monta.cor_da_zona(slug))
    except Exception:
        # `cor_da_zona` levanta `SystemExit` para colorway que o SVG não tem.
        # Derrubar a pintura da aba por causa de um modelo novo seria trocar uma
        # barra que falta por uma tela congelada.
        return ""
    # SÓ HEXADECIMAL SAI DAQUI. A guarda é por FORMA e não por lista de modelos:
    # uma lista de oito nomes envelheceria no dia em que ela medir um deles.
    return cor if re.fullmatch(r"#[0-9a-fA-F]{6}", cor) else ""


def colorway_do_controle(m: Any) -> str:
    """O modelo do mapa dela para aquele controle, ou `""` quando ninguém leu.

    É o SLUG (`white`, `galactic-purple`), e não o hex: o `<svg>` do desenho
    escolhe a cor por `data-colorway`, e a folha das 28 que a página publica
    pinta as dez zonas dele. Quem traduz código de fábrica → slug é
    `mesa_viva.CORES`, que lê `docs/data/cores-do-dualsense.csv`; a mesa já
    entrega o slug pronto em `cor`, e é só isso que sai daqui.

    O `""` É A REGRA DELA, e não uma falta: sem cor lida o alvo `atributo` faz
    `removeAttribute`, nenhuma regra da folha casa e o desenho cai no cinza cru
    do `ds_limpo.svg` — o controle SEM identidade. Deixar o `data-colorway` do
    mockup faria o contrário: mostraria o Cosmic Red do desenho sobre um
    aparelho que é outro, que é o defeito que esta leva existe para matar.
    Pelo RÁDIO isso é o caso normal — o mapa de canais responde
    `identidade.cor_do_aparelho = não`, e a resposta nunca vem.

    POR QUE NÃO REUSAR `_hex_do_plastico`: são línguas diferentes no mesmo dado.
    A barra da esquerda é pintada com um hex (alvo `cor`); o desenho é escolhido
    por nome de modelo (alvo `atributo`). Traduzir um no outro obrigaria a tela
    a procurar o slug de volta a partir da cor, que é a conta ao contrário.
    """
    return str(m.get("cor") or "")


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
        # AS DUAS CHAVES VIAJAM JUNTAS, e a que faltava aqui apagou a régua
        # inteira — 06/09/2026, `CONEXOES-LIGAR-TUDO-01`.
        #
        # `via` é a PALAVRA que a régua escreve num `title` (*"hoje no cabo"*);
        # `transporte` é a chave CRUA que :func:`_e_radio` compara. A costura da
        # ONDA B trocou o `c["via"] == "BT"` de `_regua_do_radio` por
        # `_e_radio(c)` — e `c` ali é o dicionário que ESTA função devolve, que
        # nunca carregou `transporte`. Resultado medido: `no_radio` ficava
        # SEMPRE vazio, e a régua de Desempenho mostrava zero controle no rádio
        # com o controle no rádio. **É exatamente o sintoma que o comentário da
        # troca dizia estar prevenindo** — calado, sem log; quem o revelou foram
        # as duas réguas de identidade que a costura deixou vermelhas.
        "via": str(m.get("via") or ""),
        "transporte": str(m.get("transporte") or ""),
        "plastico": _hex_do_plastico(str(m.get("cor") or "")),
        # A PONTE QUE SUBIU, e não a que se pediu. É a mesma fonte que o
        # `radio_da_mesa.ocupacao_por_adaptador` usa (`bt_mic.uniqs`), com a
        # razão escrita lá: *"uma ponte pedida que não subiu não ocupa fatia de
        # rádio nenhuma"*. O desenho mostra a fatia laranja porque na bancada a
        # ponte está de pé; aqui ela só aparece quando está mesmo.
        "mic": (norm_mac(str(m.get("uniq") or "")) or "") in com_mic,
    }


def _nomes_dos_adaptadores() -> tuple[dict[str, str], dict[str, str]]:
    """`({endereço: nome}, {hciN: nome})` — as duas chaves da MESMA leitura.

    A régua precisa das duas porque as duas pontas dela falam línguas
    diferentes: a pista COM gente é endereçada pelo endereço de rádio (é o que
    `radio_da_mesa.adaptador_por_uniq` lê do `HID_PHYS`), e a pista VAZIA é
    endereçada pelo `hciN` da varredura do sysfs (que não publica endereço
    nenhum — medido em 22/08). O `Dongle` do BlueZ é o único lugar onde as duas
    aparecem juntas, e é por isso que a junção mora aqui.

    **O ENDEREÇO NÃO SAI DAQUI PARA A TELA.** Ele é chave de casamento e mais
    nada: o que a pista escreve é o `nome`. Um MAC na tela é o que o
    `check_endereco_de_radio.py` reprova, e com razão.
    """
    dongles = _dongles()
    if not dongles:
        return {}, {}
    por_endereco: dict[str, str] = {}
    por_interface: dict[str, str] = {}
    for d in dongles:
        nome = str(getattr(d, "nome", "") or "")
        if not nome:
            continue
        endereco = str(getattr(d, "endereco", "") or "")
        if endereco:
            por_endereco[endereco] = nome
        # `/org/bluez/hci1` → `hci1`. É o único ponto em que o `hciN` é usado, e
        # ele NUNCA vai para a tela: a decisão M1 o proíbe ali porque o índice
        # inverte entre boots. Aqui ele só casa duas leituras do mesmo instante.
        interface = str(getattr(d, "objeto", "") or "").rsplit("/", 1)[-1]
        if interface:
            por_interface[interface] = nome
    return por_endereco, por_interface


# ---------------------------------------------------------------------------
# A CONTA DE SLOTS POR ADAPTADOR — "cabe o que eu quero fazer?"
# ---------------------------------------------------------------------------
#
# A RÉGUA DE CIMA MOSTRA O QUE ESTÁ; ESTA RESPONDE O QUE CABE. São perguntas
# diferentes, e a segunda não se lê de uma barra: olhar uma fatia de 260,4 em
# 1.600 não diz se o PRÓXIMO controle entra — e é essa a pergunta de quem tem
# um controle no cabo e quer trazê-lo para o rádio.
#
# O DONO É `integrations/plano_de_radio.py`, e ele já escreve TODAS as frases:
# `linha_do_cabe_mais_um` (a resposta com o "ficaria em N de M"),
# `linha_do_declarado_que_nao_subiu` (o microfone que ela marcou e que não está
# de pé) e as duas respostas honestas de `secao_orcamento` para os dois estados
# em que não há conta a fazer. **Nenhuma nasce aqui.**
#
# OS DOIS ESTADOS QUE NÃO SÃO CONTA são a metade que a régua de cima não tem, e
# a cicatriz é do dono: *"**Nunca 'Folgada'**: a cura da B1, medida em
# 23/08/2026 — com o Hefesto parado as três barras diziam 'Folgada', em verde,
# '0/1600', byte a byte a tela de um rádio vazio."* Não saber e estar vazio são
# coisas diferentes, e a diferença é a informação inteira.
#
# ESTA CONTA NÃO PERGUNTA NADA A NINGUÉM. A janela estável faz um `state_full`
# próprio por `call_async` (e o dono declara isso como dívida: *"este é o
# SEGUNDO `state_full` por entrada na aba"*). Aqui o `ctx.state` do tique já é o
# `state_full`, então o segundo pedido não existe — a dívida do dono não
# atravessa para cá.


def _conta_de_slots(ctx: Contexto) -> str:
    """As linhas do "cabe mais um?" por adaptador, ou a resposta honesta.

    A ORDEM DAS LINHAS É A DO DONO (`secao_orcamento._ContaDeSlots.falas`): por
    adaptador, o pendente antes do "cabe mais um" — o que está errado agora vem
    antes do que se pode planejar.

    **O `linha_do_plano` FICA DE FORA, e é decisão medida.** Ele diz quem está
    em qual adaptador e quanto isso custa — que é exatamente o que a régua
    logo acima desenha, com a cor do plástico de cada um. Repeti-lo em texto
    seria a segunda grafia do mesmo fato na MESMA seção, e a primeira coisa que
    uma segunda grafia perde é a revisão dela.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        NINGUEM_NO_RADIO,
        SEM_RESPOSTA_DO_DAEMON,
    )
    from hefesto_dualsense4unix.integrations import plano_de_radio

    st = ctx.state
    # SEM RESPOSTA NÃO É RÁDIO VAZIO. `state` vazio quer dizer que o serviço não
    # falou; uma lista `controllers` vazia quer dizer que ele falou e não há
    # ninguém. Confundir os dois é o defeito da B1 acima.
    if not st:
        return html.escape(SEM_RESPOSTA_DO_DAEMON)

    planos: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        bt_mic = st.get("bt_mic")
        planos = plano_de_radio.plano_por_adaptador(
            [c for c in (st.get("controllers") or []) if isinstance(c, dict)],
            com_ponte_de_mic=((bt_mic.get("uniqs") or [])
                              if isinstance(bt_mic, dict) else ()),
            mic_declarado=_mics_declarados(),
            apelidos=_apelidos_por_endereco(),
        )
    if not planos:
        return html.escape(NINGUEM_NO_RADIO)

    linhas: list[str] = []
    for _endereco, plano in sorted(planos.items()):
        pendente = plano_de_radio.linha_do_declarado_que_nao_subiu(plano)
        if pendente:
            linhas.append(html.escape(pendente))
        linhas.append(html.escape(plano_de_radio.linha_do_cabe_mais_um(plano)))
    return "<br>".join(linhas)


def _mics_declarados() -> tuple[str, ...]:
    """Os `uniq` cujo microfone ELA marcou no `maquina.json`.

    É a metade que separa as duas contas do dono (`plano_de_radio`, regra 1): o
    que SUBIU vem do daemon (`bt_mic.uniqs`), o que ela QUER vem do disco. Sem
    esta lista a tela mostraria "está tudo certo" sobre uma ponte no chão — o
    padrão que a queixa do Sackboy revelou.
    """
    declarada = _declaracao()
    if declarada is None:
        return ()
    with contextlib.suppress(Exception):
        return tuple(
            chave
            for chave, valor in (getattr(declarada, "controles", {}) or {}).items()
            if getattr(valor, "microfone", None)
        )
    return ()


def _apelidos_por_endereco() -> dict[str, str]:
    """`{endereço de rádio: o nome que ELA deu}` — a primeira metade de
    :func:`_nomes_dos_adaptadores`.

    O nome vai para a frase do "cabe mais um" pelo `plano.nome_na_tela`, e o
    `hciN` NUNCA vai: a decisão M1 o proíbe porque o índice é a vaga, não o
    aparelho, e ele inverte entre boots. Sem apelido o dono escreve **Adaptador
    sem nome**, que é palavra dele.
    """
    por_endereco, _por_interface = _nomes_dos_adaptadores()
    return por_endereco


def _chave_de_radio(endereco: str) -> str:
    """O endereço de rádio na forma que os DOIS lados podem comparar.

    **O DEFEITO QUE ISTO FECHA foi achado por ELA em 08/09/2026**, olhando a aba
    com os quatro DualSense na mesa: a régua desenhava CINCO pistas para TRÊS
    adaptadores, as três com nome apareciam vazias, e os dois controles do rádio
    caíam em duas pistas "Sem nome".

    A CAUSA É A CAIXA, e nada além dela. Medido na máquina dela:

        BlueZ  ->  'AC:A7:F1:00:00:CE'   (`org.bluez.Adapter1.Address`)
        sysfs  ->  'ac:a7:f1:00:00:ce'   (`HID_PHYS`)

    É o MESMO adaptador. O `grupos.pop(endereco)` nunca casava, então todo grupo
    sobrevivia até o ramo do "sobrou" e virava pista sem nome — ao lado das
    pistas nomeadas e vazias.

    O comentário logo abaixo AFIRMAVA a premissa falsa, palavra por palavra:
    *"o `endereco` de cada adaptador vem do BlueZ, e é a MESMA chave que o
    `adaptador_por_uniq` devolve"*. Era a mesma chave semanticamente e duas
    chaves diferentes para um `dict`.

    **E O SINTOMA JÁ TINHA APARECIDO**, por outra causa, em 06/09 — está escrito
    na função que monta os grupos. Duas causas diferentes, o mesmo desenho
    errado na tela dela: é o preço de casar por string sem uma forma canônica.
    Agora há uma, e ela é obrigatória nos dois lados.
    """
    return endereco.strip().lower()


def _endereco_do_adaptador(interface: str) -> str:
    """O endereço de rádio daquele `hciN`, pelo BlueZ. `""` = não perguntei.

    É a ponte entre a varredura do sysfs (que conhece `hciN` e a porta) e o
    medidor (que conhece endereço). Sem o BlueZ ela devolve vazio, e o efeito é
    o certo: a pista do adaptador nasce vazia em vez de receber a fatia de
    outro.
    """
    if not interface:
        return ""
    for d in (_dongles() or ()):
        if str(getattr(d, "objeto", "") or "").rsplit("/", 1)[-1] == interface:
            return _chave_de_radio(str(getattr(d, "endereco", "") or ""))
    return ""


def _e_radio(c: dict[str, object]) -> bool:
    """Este controle fala por rádio? Lê a chave CRUA, nunca a palavra da tela.

    `transporte` é `"usb"`/`"bt"` e vem de `mesa_viva.py:385`; `via` carrega a
    PALAVRA da tela ("cabo"/"rádio"), que muda com o glossário. Comparar a palavra
    faria esta aba perder os controles do rádio na primeira vez que alguém
    traduzisse a tela — calado, sem log e sem régua vermelha.

    A `ONDA4-S10-O-TRANSPORTE-01` mediu os cinco pontos e escreveu o caminho; ela
    não podia executá-lo porque este arquivo não era da posse dela. Quem fechou
    foi a costura da ONDA B, 06/09/2026.

    **QUEM CHAMAR ISTO TEM DE PASSAR UM DICIONÁRIO QUE CARREGUE `transporte`**, e
    a advertência custou um defeito vivo no mesmo dia
    (`CONEXOES-LIGAR-TUDO-01`): a troca da ONDA B aplicou esta função ao
    dicionário de :func:`_da_mesa_para_a_regua`, que só carregava a PALAVRA — e a
    régua de Desempenho passou a mostrar ZERO controle no rádio com o controle no
    rádio, que é o sintoma exato que a troca dizia estar prevenindo. Um dicionário
    sem a chave crua responde `False` sobre TUDO, calado.
    """
    return str(c.get("transporte") or "").strip().lower() == "bt"


def _regua_do_radio(ctx: Contexto) -> str:
    """A régua de Desempenho com a mesa DELA — pistas, eixo e legenda.

    O QUE O PRODUTO SABE, e é só isto: quem está no rádio (a mesa), em qual
    adaptador cada um está (`radio_da_mesa.adaptador_por_uniq`, que lê o
    `HID_PHYS` do sysfs) e quanto cada fatia custa (`radio_da_mesa`, os mesmos
    quatro números que o desenho já lia).

    **UMA PISTA POR ADAPTADOR DELA — 04/09/2026, e o que faltava era a FONTE.**
    O que estava escrito aqui dizia, com todas as letras, que o passo seguinte
    *"espera uma fonte: `radio_da_mesa` só sabe mapear `uniq` → adaptador
    (`adaptador_por_uniq`), e não sabe ENUMERAR os adaptadores"*. **Sabe outro
    módulo:** `mesa_de_radio.ler_a_mesa().adaptadores` — o mesmo que esta aba já
    lia para os rádios vizinhos, e que devolve TRÊS nesta bancada (medido em
    04/09). A régua desenhava uma pista quando havia gente no rádio e uma pista
    vazia e sem nome quando não havia; com os dois controles dela no cabo, a
    seção Desempenho respondia *"cabe mais um controle no rádio?"* mostrando UMA
    barra sobre TRÊS adaptadores.

    **E O NOME DO ADAPTADOR TAMBÉM TEM FONTE.** A outra frase que estava aqui —
    *"o apelido mora na declaração dela, endereçado por CAMINHO de barramento, e
    aqui a chave é o endereço de rádio: as duas não casam hoje"* — descrevia o
    caminho errado. O apelido **não** está no `maquina.json`: está no
    `org.bluez.Adapter1.Alias` (`secao_mesa`: *"o alias mora no BlueZ, que não
    passa pelo rascunho da máquina"*), e o `Dongle` que o traz carrega TAMBÉM o
    endereço e o `/org/bluez/hciN` — as duas pontas que faltavam. O casamento é
    endereço→nome para a pista com gente e `hciN`→nome para as vazias, e ele
    fecha porque as duas chaves saem da MESMA leitura.

    A ORDEM DAS PISTAS É A DA TABELA acima — `ler_a_mesa()` devolve os
    adaptadores em ordem de `hciN`, e é essa ordem que a tabela de "Adaptadores
    Bluetooth" mostra. Duas listas do mesmo hardware em ordens diferentes fariam
    a pessoa procurar a barra do adaptador errado.

    O ADAPTADOR QUE O SYSFS NÃO SOUBE DIZER continua ganhando pista própria, sem
    nome, e a regra é do dono: `adaptador_por_uniq` devolve `""` para o controle
    cujo `HID_PHYS` não é MAC, e *"nunca empresta o adaptador do vizinho"*.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

    com_mic = {c for c in (norm_mac(str(u)) for u in
                           ((ctx.state.get("bt_mic") or {}).get("uniqs") or [])) if c}
    todos = [_da_mesa_para_a_regua(m, com_mic) for m in ctx.mesa]
    # A COMPARAÇÃO LÊ A CHAVE CRUA, NÃO A PALAVRA — costura da ONDA B, 06/09/2026.
    # A `via` passou a carregar a palavra da tela ("cabo"/"rádio"); quem agrupa por
    # adaptador compara `transporte` ("usb"/"bt"), que o item da mesa publica ao lado
    # (`mesa_viva.py:385`). Sem esta troca, esta aba mostraria ZERO controles no rádio
    # com os dois no rádio — calado, sem log e sem régua vermelha. A S-10 mediu e
    # escreveu o caminho; ela não podia executá-lo porque este arquivo não era dela.
    no_radio = [c for c in todos if _e_radio(c)]
    no_cabo = [c for c in todos if not _e_radio(c)]

    onde: dict[str, str] = {}
    if no_radio:
        with contextlib.suppress(Exception):
            # A SEXTA COMPARAÇÃO DE `via`, e ela sobreviveu à costura da ONDA B
            # — 06/09/2026. Com a `via` carregando "rádio", esta lista nascia
            # VAZIA e `adaptador_por_uniq` recebia nada: todos os controles do
            # rádio caíam no grupo SEM_ADAPTADOR, numa pista sem nome, e as
            # pistas dos três adaptadores dela ficavam vazias ao lado.
            onde = rm.adaptador_por_uniq(
                [str(m.get("uniq") or "") for m in ctx.mesa if _e_radio(m)])

    # UM GRUPO POR ADAPTADOR, e o SEM_ADAPTADOR por último. `adaptador_por_uniq`
    # devolve `""` para quem o sysfs não soube dizer, e a regra de honestidade é
    # dele: *"nunca empresta o adaptador do vizinho"*. Aqui isso vira uma pista
    # à parte, sem nome — e não uma fatia enfiada na pista de outro.
    grupos: dict[str, list[dict[str, Any]]] = {}
    for m, c in zip(ctx.mesa, todos, strict=True):
        if not _e_radio(c):
            continue
        grupos.setdefault(
            _chave_de_radio(onde.get(str(m.get("uniq") or ""), "")), []).append(c)

    nome_por_endereco, nome_por_interface = _nomes_dos_adaptadores()
    pistas: list[dict[str, Any]] = []
    # PRIMEIRO OS ADAPTADORES QUE EXISTEM, na ordem da tabela. Cada um leva o que
    # está NELE — e quando não há ninguém, leva a pista vazia que o desenho dela
    # já traz (o `if not dentro` de :func:`html_da_regua_do_radio` escreve
    # "Nenhum controle neste rádio · 0 de 1.600").
    #
    # O `endereco` de cada adaptador vem do BlueZ e o do grupo vem do sysfs, e os
    # dois passam por `_chave_de_radio` — que existe porque eles NÃO eram a mesma
    # chave: o BlueZ escreve em maiúsculas e o sysfs em minúsculas. Um adaptador
    # que o BlueZ não listou não tem
    # como casar com o grupo, e por isso ele aparece com o que sabe de si (o
    # `hciN` → nome) e sem fatia — nunca com a fatia de outro.
    mesa = _mesa_do_radio()
    for a in tuple(getattr(mesa, "adaptadores", ()) or ()):
        interface = str(getattr(a, "interface", ""))
        endereco = _endereco_do_adaptador(interface)
        dentro = grupos.pop(endereco, []) if endereco else []
        pistas.append({
            "nome": nome_por_interface.get(interface, "") or SEM_NOME,
            "dica": "",
            "dentro": dentro,
            "vagas": no_cabo,
        })
    # E DEPOIS O QUE SOBROU: um grupo cujo endereço não bate com adaptador
    # nenhum da varredura. Ele existe — há um controle falando por ele —, e
    # calá-lo seria esconder ocupação de rádio real.
    for chave in sorted(grupos, key=lambda k: (k == "", k)):
        pistas.append({
            "nome": nome_por_endereco.get(chave, "") or SEM_NOME,
            "dica": "",
            "dentro": grupos[chave],
            "vagas": no_cabo,
        })
    if not pistas:
        # NEM ADAPTADOR NEM CONTROLE NO RÁDIO — E ISSO NÃO PODE VIRAR UM EIXO
        # SOZINHO.
        #
        # O DEFEITO, fotografado na mesa dela em 03/09/2026 com o White no cabo
        # e nada no rádio: `grupos` nasce dos controles que estão NO RÁDIO, e
        # sem nenhum ele fica vazio, `pistas` fica vazia e o bloco inteiro sai
        # com uma `.eixo` e uma `.leg` e MAIS NADA. A seção "Desempenho · o
        # rádio de cada adaptador, em turnos" renderizava a escala 0…1.600 e a
        # legenda anunciando `+16,3` e `+276,7` sobre ZERO barra — números com
        # cara de medição e sem nada a que pertencer. Medido no WebKit:
        # `querySelectorAll('.bloco')` devolveu 0 e `.pista` devolveu 0.
        #
        # ESTE RAMO ENCOLHEU em 04/09: ele só é alcançado quando a varredura do
        # barramento FALHOU (`_mesa_do_radio()` devolve `None`) e não há
        # ninguém no rádio. Com a varredura de pé, o laço acima já dá uma pista
        # a cada adaptador dela.
        #
        # O NOME FICA VAZIO DE PROPÓSITO. Sem leitura não se sabe QUAL adaptador
        # é — e ela tem três. Escrever `Sem nome` aqui afirmaria "existe UM
        # adaptador, e ele não tem apelido"; a coluna vazia não afirma nada, e
        # os 96 px do `.pista .quem` seguram o alinhamento com o eixo do mesmo
        # jeito.
        pistas = [{"nome": "", "dica": "", "dentro": [], "vagas": []}]
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
    (`profiles/schema.py:1661-1722`), logo é o que está no disco; procurar por
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


# ---------------------------------------------------------------------------
# O ALVO DE SAÍDA, LIDO DE VOLTA — 06/09/2026, `CONEXOES-LIGAR-TUDO-01`.
#
# O GESTO ESCREVIA E A TELA NUNCA CONFERIA. `alvo` chama
# `controller.target.set`, o daemon obedece, e no tique seguinte a tela
# continuava apontando o P1 — o `checked` do desenho, cravado no HTML. Ela
# clicava "só este" no P2, o rádio do acordeão não se mexia, e a fita do topo
# junto com ele: as regras `body:has(#gc-pN:checked) .fita .chip:nth-child(n)`
# do gerador fazem o destaque da fita seguir o acordeão, então **os dois
# lados da queixa eram o mesmo elemento**.
#
# O DOCSTRING DO GESTO DIZIA QUE ISTO ERA DO PILOTO — *"a fita do topo não se
# move […] quem mudar isso é o piloto, não este pacote"* —, e a metade que
# importa está errada: o piloto monta a fita sem `alvo`, sim, mas o DESTAQUE
# não vem do `.on` que ele escreve; vem do `:checked` do acordeão, que é desta
# aba. Substituído no lugar, e não guardado ao lado.
#
# ELE SÓ PÔDE NASCER AGORA porque o alvo `marcado` é de 04/09
# (`PINTOR-MARCADO-01`, decisão dela: *"décimo alvo `marcado`"*) — antes dele
# nenhum dos nove alvos tocava `el.checked`, e o `valor` num `<input
# type=radio>` escreve a string `"on"`, não o estado.
# ---------------------------------------------------------------------------
#: O RÓTULO DO "TODOS" NA LISTA DO ACORDEÃO. É o primeiro `<input>` do desenho
#: (`#gc-todos`), e no daemon ele é `index: null` — o broadcast
#: (`ipc_handlers.py:4134`: *"`index` null volta ao broadcast (padrão)"*).
TODOS_NA_TELA = "todos"


def _pref_do_alvo(ctx: Contexto) -> str:
    """Qual lugar da mesa a saída está mirando — `p1`..`p4`, ou `todos`.

    **A CONVERSÃO É O PONTO INTEIRO, e ela tem duas ordens diferentes.** O
    daemon guarda `output_target_index`, que é a POSIÇÃO em `controllers`
    ("0 = primário", `ipc_handlers.py:4399`); o desenho endereça por `pref`, que
    é a posição na mesa ORDENADA POR NÚMERO DE IDENTIDADE
    (`mesa_viva.mesa_do_estado:373`). As duas coincidem na mesa de um controle e
    divergem na primeira em que o primário não for o de menor número — é a mesma
    armadilha que `_indice` documenta do lado do gesto, e a ponte entre as duas
    é o `uniq`.

    `None` NO DAEMON É "TODOS", e não "não sei": o campo nasce nulo e é isso que
    o broadcast significa. Um alvo que o `state` não sabe traduzir (índice fora
    da lista, entrada sem `uniq`, controle que saiu da mesa entre um tique e
    outro) devolve `""` — **e o vazio não marca nada**, que é diferente de
    marcar "todos": desmarcar os cinco deixa a tela sem afirmar nada, e marcar o
    "todos" afirmaria um broadcast que o daemon não disse.
    """
    st = ctx.state
    if "output_target_index" not in st:
        return ""
    indice = st.get("output_target_index")
    if indice is None:
        return TODOS_NA_TELA
    if not isinstance(indice, int) or isinstance(indice, bool):
        return ""
    lista = st.get("controllers") or []
    uniq = ""
    for posicao, c in enumerate(lista):
        if not isinstance(c, dict):
            continue
        dele = c.get("index")
        seu = dele if isinstance(dele, int) and not isinstance(dele, bool) else posicao
        if seu == indice:
            uniq = str(c.get("uniq") or "")
            break
    if not uniq:
        return ""
    for m in ctx.mesa:
        if str(m.get("uniq") or "") == uniq:
            return str(m.get("pref") or "")
    return ""


def _alvo_de_saida(ctx: Contexto) -> list[str]:
    """`sim`/`""` para os CINCO rádios do acordeão, na ordem em que eles nascem.

    A ORDEM É A DO DOM, e é o contrato da lista: o piloto distribui uma lista
    pelos elementos de mesmo `data-campo` na ordem em que os acha
    (`hefesto_vivo.pintar`, passo 1). O gerador escreve `#gc-todos` primeiro e
    depois um por lugar da mesa, então esta lista é `[todos, p1, p2, p3, p4]`.

    **VAI EM TODO TIQUE, INCLUSIVE TODA VAZIA** — a mesma regra do botão cinza
    da ONDA0-F e das duas listas do ⊘: a chave que só aparece quando há o que
    dizer deixa na tela a marca do tique anterior, e um acordeão que abrisse
    sozinho num lugar sem dono seria a tela afirmando o que não é.
    """
    onde = _pref_do_alvo(ctx)
    lugares = [TODOS_NA_TELA, *sorted(TODOS_OS_LUGARES)]
    return ["sim" if onde and lugar == onde else "" for lugar in lugares]


# ---------------------------------------------------------------------------
# OS QUATRO AVISOS QUE A CASA SABIA E A TELA NÃO DIZIA — 06/09/2026.
#
# Os quatro são a mesma forma: **o dono existe no produto, com a frase pronta,
# e o HTML não tinha onde escrever**. Nenhum deles inventa texto — os dois
# primeiros vêm do `state_full` pelos donos de `app/actions/`, e os dois
# últimos da leitura do barramento pelos donos de `secao_mesa`.
#
# TODOS SÃO LINHA DE RESSALVA (`monta.ressalva`, a D-02 dela): em repouso não
# ocupam um pixel (`.ressalva:has(.nada){display:none}`), e no estado estranho
# nascem ao lado do valor. É por isso que os quatro podem entrar juntos sem que
# a "Nada se perdeu" desta aba pague altura nenhuma.
# ---------------------------------------------------------------------------
def _sem_valor() -> str:
    """`monta.NADA_A_DIZER` — o marcador que faz a `.ressalva` SUMIR.

    **NUNCA `""`**, e a razão é do piloto: `escrever()` troca vazio por
    travessão antes de olhar o alvo, então uma ressalva vazia viraria uma linha
    com um `—` — que ocupa altura para não dizer nada. É a mesma cura que o
    `+N` do exame já pagou em 06/09.
    """
    return str(_monta().NADA_A_DIZER)


def _frase_do_sem_driver(st: dict[str, Any]) -> str:
    """*"Um controle está ligado, mas o sistema não conseguiu entregá-lo…"*.

    O DONO É `status_actions.texto_de_controle_nao_adotado`, e ele já devolve
    `""` para todos os casos em que não há o que dizer — daemon sem resposta,
    payload torto, daemon antigo sem a chave, quantidade zero. A tela não
    repete nenhuma dessas guardas: repeti-las seria a segunda grafia da mesma
    regra, e a primeira coisa que uma segunda grafia perde é a revisão dela.

    **O QUE ISTO SUBSTITUI ERA EMISSÃO MORTA EM DOIS NÍVEIS**, medido em
    04/09: o pacote emitia `"sem_driver": st.get("controles_sem_driver")`, que
    é um `dict` — e `pacotes.normalizar` descarta dicionário antes da tela —,
    para um endereço que página nenhuma tinha. O defeito que este aviso cura
    (dois DualSense ligados, a janela mostrando um, e nenhuma pista do porquê)
    voltava inteiro no HTML.
    """
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.status_actions import (
            texto_de_controle_nao_adotado,
        )

        return texto_de_controle_nao_adotado(st) or _sem_valor()
    return _sem_valor()


def _frase_do_radio_fragil(st: dict[str, Any]) -> str:
    """O aviso do Bluetooth nativo frágil, **com os números** dos controles.

    DOIS DONOS, E É O DESENHO DELES: `home_actions.controles_bt_frageis` lê a
    lista publicada e `texto_native_bt_fragil` a vira frase — e a regra que
    separa os dois está escrita lá: *"lista vazia não quer dizer 'nenhum
    frágil' — quer dizer 'não sei quais'"*, e por isso quem chama olha TAMBÉM o
    booleano `native_bt_fragil`. O aviso acende sem nomes nesse caso, em vez de
    calar.

    O PACOTE JÁ EMITIA `fragil` POR CONTROLE, e continuava sem endereço: um
    booleano por cartão diria QUAL, e não O QUE FAZER. A frase do dono diz as
    duas coisas — quem é e qual é a saída (o cabo, ou voltar à emulação) —, e é
    ela que a aba Início acende.
    """
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.home_actions import (
            controles_bt_frageis,
            texto_native_bt_fragil,
        )

        if not st.get("native_bt_fragil"):
            return _sem_valor()
        return texto_native_bt_fragil(controles_bt_frageis(st)) or _sem_valor()
    return _sem_valor()


#: AS DUAS LEITURAS DO GABINETE, na mesma regra do `_MESA_DO_RADIO`: varredura
#: de barramento e leitura de disco entram UMA VEZ e são renovadas pelo
#: **Examinar Portas**, nunca por tique. Medido nesta bancada em 06/09/2026:
#: `listar_entradas()` custa **6,3 ms** e devolve 38 nós; `ler_do_disco()` custa
#: **0,11 ms**. Os 6 ms caberiam no tique de 500 ms — e é exatamente o
#: raciocínio que o bloco "O QUE SE LÊ DA MÁQUINA" proíbe: pendurar uma
#: varredura de `/sys` num tique é gastar CPU para reler o que não muda.
#:
#: `None` = ainda não lido, e é diferente de tupla/dicionário vazios: "não
#: perguntei" não pode virar "o seu gabinete não tem entradas".
_ENTRADAS: Any = None
_GABINETE: Any = None


def _entradas(recarregar: bool = False) -> Any:
    """Os nós de entrada do gabinete, **inclusive os vazios** — ou `()`.

    É a TERCEIRA varredura de `/sys` desta aba, e ela responde o que as outras
    duas não sabem: **uma entrada vazia não tem aparelho**, logo não aparece nem
    em `ler_a_mesa` nem em `ler_o_barramento`. É ela que sustenta o *"há entrada
    livre em outro caminho"* do conselho do hub — sem entradas, o conselho não
    nasce, que é o desenho certo: um conselho que não sabe para onde mandar não
    é conselho.
    """
    global _ENTRADAS
    if _ENTRADAS is None or recarregar:
        try:
            perfil._com_o_src()
            from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
                listar_entradas,
            )

            _ENTRADAS = tuple(listar_entradas())
        except Exception:
            return ()
    return _ENTRADAS


def _gabinete(recarregar: bool = False) -> Any:
    """O `gabinete.json` que o install gravou — `{}` quando não há.

    ELE É A ÚNICA FONTE DA TABELA SMBIOS TIPO 8, e o motivo é de permissão: o
    arquivo do DMI é `400 root`, esta janela é sudo-zero, e quem o leu foi o
    install, uma vez, como root. Aqui só se abre o que ele deixou —
    `ler_do_disco` já engole arquivo ausente, truncado e de formato futuro.
    """
    global _GABINETE
    if _GABINETE is None or recarregar:
        try:
            perfil._com_o_src()
            from hefesto_dualsense4unix.integrations.censo_do_gabinete import (
                ler_do_disco,
            )

            _GABINETE = ler_do_disco()
        except Exception:
            return {}
    return _GABINETE


def _frase_do_hub() -> str:
    """O hub que está acima de TODOS os adaptadores — fato, por quê e conselho.

    O DONO É `secao_mesa._frase_do_hub_em_comum`, e ele responde com as TRÊS
    frases ou com o silêncio das três. A regra que ele guarda é a que a coluna
    "Onde está" não consegue guardar: aquela escreve *"Em hub"* linha a linha e
    **nunca compara as linhas entre si**; quem compara é
    `censo_do_barramento.hub_em_comum`, que sobe a cadeia em vez de olhar o pai.

    **O CONSELHO É A METADE OPCIONAL**, e ele só nasce quando há para onde
    mandar — buraco livre, alcançável com a mão, numa controladora DIFERENTE.
    Três adaptadores no mesmo hub é o arranjo que o próprio guia de rádio manda
    comprar: o fato sozinho não é queixa.

    MEDIDO NESTA BANCADA EM 06/09/2026: os três adaptadores dela estão em
    `usb1/1-4`, `usb3/3-1/3-1.2` e `usb3/3-1/3-1.4` — **não há hub acima dos
    três**, e a linha CALA. É o estado certo, e é o que a foto mostra.
    """
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
            _frase_do_hub_em_comum,
        )

        mesa, censo = _mesa_do_radio(), _censo()
        if mesa is None or censo is None:
            return _sem_valor()
        frases = [f for f in _frase_do_hub_em_comum(mesa, censo, _entradas()) if f]
        if frases:
            return "<br>".join(frases)
    return _sem_valor()


def _frases_do_gabinete() -> str:
    """As contagens de entrada LADO A LADO, mais a pergunta — nunca uma escolha.

    O DONO É `secao_mesa._linhas_do_gabinete`, e a regra inteira é dele: o que o
    firmware conta e o que o kernel conta vão os DOIS, e o produto **não
    escolhe** entre eles. Escolher desenharia um gabinete que ninguém tem, e a
    pessoa procuraria na traseira buracos que o mapa não mostra.

    SEM `gabinete.json` — primeira instalação, ou install anterior a 25/08 — a
    resposta é o silêncio, e a seção fala como falava antes. Firmware é FONTE,
    nunca premissa.

    MEDIDO NESTA BANCADA EM 06/09/2026: a BIOS conta **5** entradas USB e o
    barramento conta **15** buracos; as duas discordam, e a terceira linha é a
    pergunta que só ela pode responder. Sem esta linha, o mapa do gabinete
    desenhava a traseira dela sem dizer quantos buracos ela deveria ter.
    """
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
            _linhas_do_gabinete,
        )

        linhas = [f for f in _linhas_do_gabinete(_gabinete()) if f]
        if linhas:
            return "<br>".join(linhas)
    return _sem_valor()


@registrar("08-conexoes.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    global _ORDENS_NA_TELA, _VIZINHOS
    st = ctx.state
    # O EXAME COMPLETO PEDIDO UMA VEZ, ANTES DE LER A TIRA. Ele corre em thread
    # e não bloqueia este tique — o que ele traz aparece no tique seguinte, que
    # é a mesma latência que a janela estável tem. Ver
    # `_pedir_o_exame_de_entrada`: sem isto, duas das cinco linhas do Check-up
    # nasciam vazias e a ordem de serviço da tela era a do mockup.
    _pedir_o_exame_de_entrada()
    vivos = _itens_da_tela()
    itens = [_linha(i) for i in vivos]
    # A PONTE ENTRE O CLIQUE E A ORDEM, e ela se refaz a cada pintura: o ⊘ da
    # posição N age sobre o que foi PINTADO na posição N. Guardar a lista aqui,
    # e não montá-la no gesto, é o que garante que as duas concordem — se a
    # tira mudar entre a pintura e o clique, o clique age sobre o que ela
    # estava vendo, que é o único alvo defensável.
    _ORDENS_NA_TELA = tuple(getattr(i, "ordem", None) for i in vivos)
    # O QUE SOBRA NÃO É CLICÁVEL, MAS PASSOU A SER DITO — 06/09/2026, decisão
    # 08-Q7 dela: *"Quando sobra, a lista ganha uma última linha curta"*. O
    # desenho tem CINCO linhas de exame (`TETO_DO_EXAME`) e QUATRO blocos de
    # vizinho (`TETO_DE_VIZINHOS`); se a mesa dela render mais, a pintura
    # escreve nos lugares que existem e os endereços `exame-mais` e
    # `vizinho-mais` dizem quantos não couberam. Nenhum clique age sobre o alvo
    # errado (o `data-v` só vai até o teto e o `_slot` confere a faixa).
    #
    # **A DÍVIDA QUE ISTO FECHA ESTAVA ESCRITA AQUI**, e o comentário que a
    # descrevia — *"Aqui não há onde dizer ainda"* — foi substituído em vez de
    # guardado ao lado: o Hefesto não descreve a limitação, ele constrói o
    # mecanismo que a remove (10-Q6).

    adap = _adaptadores(ctx.conectados, ctx.state)
    declaracao = _declaracao()

    # OS VIZINHOS SÃO OS DELA, e não os quatro do desenho. Enquanto eram os do
    # desenho, o `<select>` "— O que é? —" só podia gravar no `maquina.json`
    # dela um rádio da bancada de exemplo — a razão pela qual este gesto passou
    # a primeira leva sem dono.
    radios = tuple(getattr(_mesa_do_radio(), "radios", ()) or ())
    _VIZINHOS = tuple(_chave_do_radio(r) for r in radios)
    para_id, rotulo_do_tipo = _tipos_de_radio()
    pergunta = _a_pergunta()
    declarados = _radios_declarados(declaracao)
    vizinho_nome, vizinho_tipo, vizinho_pergunta = [], [], []
    # `strict=True` E NÃO POR ESTILO: as duas saem do MESMO `radios` duas
    # linhas acima, então um comprimento diferente aqui quer dizer que alguém
    # passou a montar `_VIZINHOS` noutro lugar — e o `zip` frouxo apagaria os
    # rádios do fim em silêncio, que é o pior desfecho numa lista que endereça
    # o clique dela por POSIÇÃO.
    for chave, radio in zip(_VIZINHOS, radios, strict=True):
        # `vid:pid` É O NOME QUE O PRODUTO TEM. A GUI estável escreve o mesmo
        # (`gui/aba_conexoes.html_dos_vizinhos`), e a tela já explica por quê:
        # *"o sistema entrega o nome cru e não sabe o que é"*. Um nome bonito
        # aqui seria adivinhação a partir do vid.
        vizinho_nome.append(chave)
        # A TELA SUGERE, ELA CONFIRMA — decisão dela de 03/09/2026, e a razão
        # está em :data:`_SUGESTAO_DO_KERNEL`. Enquanto ela não respondeu, a
        # primeira opção do `<select>` deixa de ser "— O que é? —" seco e passa
        # a carregar o que o kernel LEU, ainda como pergunta: "— Teclado? —".
        #
        # A RESPOSTA DELA VENCE O KERNEL, SEMPRE, e é a mesma precedência da
        # janela estável (`secao_mesa._celula_do_que_e`): declarado primeiro, o
        # que o kernel leu depois, e a pergunta seca quando ninguém sabe. Com
        # ela respondida a primeira opção volta a ser a pergunta — a sugestão
        # não pode ficar por cima do que ela disse.
        respondido = rotulo_do_tipo.get(declarados.get(chave, ""), "")
        sugerida = ("" if respondido
                    else _sugestao_do_vizinho(str(getattr(radio, "no", "")), para_id))
        primeira = _pergunta_sugerida(sugerida, pergunta) if sugerida else pergunta
        vizinho_pergunta.append(primeira)
        vizinho_tipo.append(respondido or primeira)
    # O QUE NÃO CABE AQUI, E FICA NOMEADO: a borda CIANO de "o produto não sabe
    # o que é isto" (`select.pronto.pergunta`) está CRAVADA no desenho — dois
    # dos quatro blocos, para sempre — e nunca é repintada. Na mesa desta casa
    # os QUATRO rádios estão sem resposta e só DOIS aparecem em ciano: a tela
    # afirma conhecer dois rádios sobre os quais o produto nada sabe. É a mesma
    # família do `sala-altura` de 03/09.
    #
    # A CURA CUSTA UMA REGRA DE CSS — mover a classe do `<select>` para a
    # `.viz` que o embrulha, para o alvo `classe` do pintor alcançá-la, e
    # trocar o seletor por `.viz.pergunta select.pronto`. Zero pixel se move, e
    # ainda assim o `check_o_desenho_aprovado` a lê como DESENHO (o `INVISIVEIS`
    # apaga endereço, não classe nem folha de estilo) — logo é decisão dela, e
    # não se faz por conta própria. O texto da opção já diz o essencial sem ela:
    # `— Teclado? —` não se confunde com `Teclado`.

    # O TETO DA VIBRAÇÃO TEM TRÊS FONTES, E DUAS DELAS SE CHAMAVAM "O GLOBAL"
    # — corrigido em 01/09/2026, e foi o defeito que segurou esta leva:
    #
    #   perfil.rumble.policy   o DENOMINADOR do fator por peça
    #                          (`profiles/manager.py:1857`)
    #   state['rumble_policy'] o que MULTIPLICA no funil do motor
    #                          (`daemon/ipc_handlers.py:2923` → `_effective_mult`)
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

    # A SONDA DA MESA SUJA, UMA VEZ POR TIQUE e não uma por controle: ela
    # responde sobre a MÁQUINA ("alguém está segurando nó de controle agora?"),
    # não sobre um aparelho. Chamá-la dentro do laço varreria `/proc` uma vez
    # por cartão para receber a mesma resposta.
    mesa_suja = _mesa_suja()

    # UM PASSO DO RELÓGIO DA ESPERA, UMA VEZ POR TIQUE — ver a seção "A ESPERA
    # PELO PS". Ele vem antes do laço porque a espera é do RELÓGIO, não do
    # cartão: chamá-lo por controle entregaria N tiques por segundo ao dono numa
    # mesa de N, e a contagem correria mais rápido quanto mais cheia a mesa.
    #
    # A LISTA VAI JUNTO por uma razão só, e ela está no docstring: quem VOLTOU
    # perde o recado de "não voltou". Sem isto a frase envelheceria na tela — e
    # uma tela que afirma o que já não é verdade é o mesmo defeito que esta
    # sprint veio fechar, do outro lado.
    _correr_as_esperas({norm_mac(str(c.get("uniq") or "")) or ""
                        for c in ctx.conectados})

    colunas = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        teto_campo, teto_frase = _teto_do_controle(overrides, uniq, vibracao, sem_dono)
        eu = da_mesa.get(uniq) or {}
        colunas[uniq] = {
            "via": (c.get("transport") or "").upper(),
            # A BATERIA COMO A TELA A ESCREVE — `Controle.texto_da_bateria`, o
            # dono (`gui/aba_conexoes.py:245`), que põe o TRAVESSÃO quando
            # ninguém leu em vez de um número herdado. Ela era o `battery_pct`
            # CRU, e um inteiro num endereço de texto escreveria `100` onde o
            # desenho promete `100%` — e `null` onde ele promete `—`.
            #
            # ATÉ 03/09/2026 ISSO NÃO APARECIA porque a página não tinha
            # endereço para `bateria`: a linha fechada dizia "Bateria 100%" e
            # "Bateria 64%" — os dois números do mockup — acontecesse o que
            # acontecesse. A dica desta aba manda ler na aba Controles, onde ela
            # É pintada; o número errado continuava aqui do mesmo jeito.
            "bateria": _texto_da_bateria(c.get("battery_pct")),
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
            # O DESENHO PEQUENO DA LINHA — `IDENTIDADE-VEM-DE-CIMA`, 03/09/2026.
            # Ver :func:`colorway_do_controle`: vai o SLUG do modelo, que é o
            # que o `data-colorway` do `<svg>` fala, e não o hex.
            "desenho": colorway_do_controle(eu),
            "ponte": bool(c.get("uniq") in (st.get("pontes_confirmadas") or {})),
            "fragil": bool(c.get("uniq") in (st.get("native_bt_fragil_controles") or [])),
            # O QUE ESTÁ DECLARADO, e não o que o desenho traz. O `<select>`
            # nasce em "Ligado" no HTML; sem esta linha, desligar a ponte
            # gravava no disco e a tela continuava dizendo "Ligado" — e o
            # segundo clique dela pareceria o primeiro.
            "mic-existe": "Ligado" if _mic_declarado(declaracao, uniq) else "Desligado",
            # POR ONDE O MICROFONE CHEGA — ver :func:`caminho_do_microfone`. A
            # linha fechada dizia "pelo cabo · Placa do controle" no primeiro
            # lugar e "pelo rádio · Pela ponte" no segundo, os dois do desenho:
            # com um controle só na mesa, o que ela lia era a cena do mockup.
            # E o `<b>Ligado</b>` ao lado dele era pior — com a ponte
            # DESLIGADA no `maquina.json` dela (medido em 03/09), a tela
            # afirmava "Ligado" sobre um microfone que nenhum programa enxerga.
            # O `mic-existe` acima já resolve o segundo: o desenho ganhou o
            # mesmo endereço no `<b>`, e o piloto distribui por `data-campo`.
            "mic-caminho": caminho_do_microfone(str(c.get("transport") or "")),
            # A TRAVA DO "A luz não acende" — ver :func:`trava_da_luz`. O botão
            # nascia apagado no P1 e aceso no P2 porque foi assim que o mockup
            # os desenhou; agora ele apaga no CABO e acende no RÁDIO, que é a
            # mesma condição que o gesto usa para recusar depois do clique.
            "luz-trava": trava_da_luz(str(c.get("transport") or "")),
            # A DICA DO MESMO BOTÃO, e ela é a metade que a cor não conta — ver
            # :func:`dica_da_luz`. O `title` do desenho é congelado: o cartão da
            # esquerda explica o cabo e o da direita explica o rádio, e os dois
            # continuam explicando isso quando o controle troca de transporte.
            # Junto vêm o AVISO DA MESA SUJA (quando outro programa segura nó de
            # controle agora) e a RAZÃO do carimbo de nascimento — os dois com
            # dono no produto e zero leitor no HTML até hoje.
            "luz-dica": dica_da_luz(str(c.get("transport") or ""),
                                    c.get("nascimento"), mesa_suja),
            # O RÓTULO DO BOTÃO, e é ele que cumpre a promessa do `title`: na
            # espera o mesmo botão diz "Cancelar". Ver :func:`texto_do_botao_da_luz`.
            "luz-texto": texto_do_botao_da_luz(uniq),
            # A LINHA DA ESPERA — o pedido do PS com a contagem enquanto ela
            # corre, e o recado do fim depois. Em repouso ela não ocupa nada
            # (`monta.ressalva`). Ver :func:`linha_da_espera`.
            "luz-espera": linha_da_espera(uniq),
            # O `title` DA LINHA DO MICROFONE — ver :func:`dica_do_microfone`. O
            # `+16,3 turnos` era digitado no desenho; agora é derivado das
            # constantes do medidor, que é de onde a barra de Desempenho já
            # tirava os dela.
            "mic-dica": dica_do_microfone(str(c.get("transport") or "")),
            # O `?` DO TETO VAI SEMPRE, e o campo só quando há o que escolher.
            # Pintar só a caixa deixaria a tela dizendo "30% da força" no campo
            # e "este controle segue o global" na dica — uma contradição NOVA,
            # nossa. O contrário (só a dica) é o caso declarado em `sem_dono`.
            "teto-explica": teto_frase,
        }
        if teto_campo is not None:
            colunas[uniq]["teto-da-vibracao"] = teto_campo
    # UMA LEITURA SÓ, e ela é a razão de esta linha não estar dentro do
    # dicionário: a `cobertura` conta os campos da confissão, e chamar a função
    # duas vezes releria o barramento no mesmo tique.
    confissao = _confissao_do_mapa()
    # PELA MESMA RAZÃO DA CONFISSÃO: a `cobertura` conta os campos do veredito, e
    # chamar `_veredito_do_exame` duas vezes refaria a conta do cabeçalho no
    # mesmo tique.
    veredito = _veredito_do_exame(vivos)
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
        # A CONFISSÃO DO DESENHO, e ela é a da MESA DELA — ver
        # :func:`_confissao_do_mapa`. A `.mm-conf-linha` mora FORA do
        # `.mm-faces` que a linha acima troca, e por isso nunca era repintada:
        # dizia "três coisas" com os três itens cravados no `title`, sobre uma
        # bancada que tem UMA lacuna. Confessar a mais manda ela procurar o que
        # o produto já sabe.
        **confissao,
        # A ORDEM DE SERVIÇO DA MÁQUINA DELA — 03/09/2026, `MIGRA-08-01`. Ver
        # `_html_da_ordem`: o card era HTML cravado no mockup mandando mover o
        # adaptador da Entrada 3 para a Entrada 9, com de→para e ganho, sobre
        # uma máquina que ninguém tinha examinado.
        #
        # E A COLUNA CRESCEU EM 04/09/2026 — as decisões [03], [04] e [07] do
        # PO. `vivos` VAI JUNTO de propósito: é a mesma lista que pintou a tira
        # à esquerda, e as duas metades da seção têm de falar do mesmo exame.
        "ordem": _html_da_ordem(vivos),
        # A CONTAGEM DA SEÇÃO, pelo dono da frase
        # (`gui.aba_conexoes.texto_da_contagem`). Ela era `2 na mesa • 1 no cabo
        # • 1 no rádio` cravado — com um controle só na mesa, a seção continuava
        # dizendo 2/1/1. É o mesmo defeito que o `topo()` já curou no cabeçalho.
        "conta-gestao": html_da_conta(
            _tela_da_aba().texto_da_contagem(
                _tela_da_aba().controles_do_estado(st))),
        # AS DUAS RESPOSTAS DELA SOBRE A SALA — ver `_sala_na_tela`. A tela
        # dizia que ela não tinha respondido a visada; o `maquina.json` dela diz
        # que respondeu.
        **_sala_na_tela(declaracao),
        # A RÉGUA DO RÁDIO INTEIRA, pelo dono único. Ver
        # `html_da_regua_do_radio`: o `title` de cada fatia nomeia o plástico, e
        # `title` não tem alvo no piloto — o bloco tem de nascer do produto.
        "regua-do-radio": _regua_do_radio(ctx),
        # A CONTA DE SLOTS POR ADAPTADOR — 06/09/2026. A régua acima mostra o
        # que ESTÁ; esta linha responde o que CABE, que é a pergunta de quem
        # tem um controle no cabo e quer trazê-lo. Ver :func:`_conta_de_slots`.
        "conta-de-slots": _conta_de_slots(ctx),
        # A TABELA DOS ADAPTADORES — 04/09/2026. Ela era HTML fixo do mockup
        # ("Sala / TP-Link UB500 / Entrada 3 · traseira" e "Sem nome / Intel
        # AX211 / Interno · M.2") sobre uma bancada com TRÊS adaptadores. É
        # trocada INTEIRA pela mesma razão da régua e do mapa: quantas linhas
        # existem é o que a máquina dela responde, e não há endereço para uma
        # `<tr>` que ainda não nasceu.
        "adaptadores-tabela": _html_dos_adaptadores(),
        # OS CONTROLES QUE O HEFESTO SÓ VÊ — EXTERNOS-01, 06/09/2026, linha 305
        # de `docs/data/paridade-gtk-html.csv`. Ver :func:`_html_dos_externos`.
        "externos-lista": _html_dos_externos(ctx),
        # O QUE O BOTÃO FÍSICO DO MICROFONE CALA — **D-12**, e é a resposta que
        # substitui o `<select>` morto de `mic-escopo`. Um valor por MÁQUINA num
        # endereço por máquina; era um por controle num campo que o produto não
        # tem como guardar por controle.
        "mic-escopo": escopo_do_botao_do_mic(st),
        # AS TRÊS LISTAS SÃO O QUE A TELA MOSTRA, uma por bloco de achado: o
        # selo, a frase e o `?`. Elas se distribuem pelos elementos de mesmo
        # `data-campo`, na ordem — o gerador não precisa saber quantos achados
        # o exame vai devolver.
        "selo": [i["selo"] for i in itens],
        # O QUARTO SELO — decisão dela, 02/09/2026: *"o que está quebrado agora
        # não pode parecer igual ao que só podia estar melhor"*. O `Item` tem
        # QUATRO estados e a tela tinha TRÊS cores: `atencao` e  # (noqa-acento): nome de estado
        # `problema`
        # caíam os dois na pílula laranja, pela mesma palavra do dono
        # (`SELO_DO_ESTADO`).
        #
        # O QUE VAI DAQUI É O ESTADO CRU, e não a classe CSS. Quem traduz
        # estado em cor é o DESENHO: cada pílula do gerador leva
        # `data-hef-alvo="classe" data-hef-classe="grave"
        # data-hef-quando="problema"`, e o `escrever()` do piloto acende a
        # classe na linha cujo estado casar (`hefesto_vivo.py:499`). Emitir a
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
        # A LINHA CALADA, E O VERBO DO ⊘ — decisão 08-Q5 dela, 06/09/2026.
        #
        # SÃO DUAS LISTAS E NÃO UMA porque são dois alvos em dois elementos: o
        # `<div class="exame">` acende a classe `apagada` pelo alvo `classe`
        # (`data-hef-quando="sim"`), e o `<button class="ignora">` recebe o
        # `title` pelo alvo `atributo`. Um elemento tem UM `data-campo`, e a
        # cor da linha e a dica do botão são dois dados diferentes.
        #
        # AS DUAS VÃO EM TODO TIQUE, inclusive vazias — a mesma regra do botão
        # cinza da ONDA0-F. Emitir `calada` só quando for `"sim"` deixaria a
        # linha que VOLTOU com a tinta do tique anterior, cinza para sempre.
        "exame-calada": [i["calada"] for i in itens],
        "ignorar-dica": [i["dica-do-ignorar"] for i in itens],
        # OS DOIS `+N` — decisão 08-Q7. Ver :func:`_o_que_nao_coube`.
        **_o_que_nao_coube(itens, vizinho_nome),
        # O CARIMBO do topo do Check-up — publicado no mesmo dia e pela mesma
        # decisão, e também já pintado.
        "examinado": _carimbo_do_exame(),
        # A RESPOSTA EM UMA LINHA — **S-09, D-16**. Ver :func:`_veredito_do_exame`.
        # O carimbo acima diz QUANDO; esta linha diz O QUÊ, e na cor do pior
        # achado. O dicionário pode vir VAZIO, e o vazio é resposta: sem exame
        # não há juízo, e um travessão numa linha de veredito seria a tela
        # afirmando um nada.
        **veredito,
        "vizinho-nome": vizinho_nome,
        # A ORDEM DESTES TRÊS IMPORTA, e é a única coisa neste dicionário em
        # que ela importa: `vizinho-pergunta` reescreve o TEXTO da primeira
        # `<option>`, e o alvo `valor` do `<select>` logo abaixo só aceita o que
        # a caixa OFERECE (`hefesto_vivo.escrever`: `o.text === t`). Emitido
        # depois, a escrita do valor cairia num texto que ainda não existe e
        # seria descartada calada — a tela pegaria a sugestão só no tique
        # seguinte. `Object.entries` preserva a ordem de inserção nos dois
        # lados, e é dela que a pintura de UM tique depende.
        "vizinho-pergunta": vizinho_pergunta,
        "vizinho-tipo": vizinho_tipo,
        # ONDE CADA RÁDIO VIZINHO ESTÁ, e o AVISO DE VIZINHANÇA junto — ver
        # :func:`_onde_dos_vizinhos`. É o mesmo fato que a linha do Check-up
        # chama de "dois rádios da bancada estão em entradas vizinhas"; aqui ele
        # aparece ao lado do rádio CULPADO, que é a metade que faltava para a
        # frase do exame ter endereço na mesa.
        "vizinho-onde": _onde_dos_vizinhos(_mesa_do_radio()),
        "vizinho-onde-dica": _dicas_dos_vizinhos(_mesa_do_radio()),
        "exame": itens,
        "achados": len(itens),
        "graves": sum(1 for i in itens if i["grave"]),
        "adaptadores": adap,
        # QUAL CONTROLE A SAÍDA ESTÁ MIRANDO — ver :func:`_alvo_de_saida`. Ela
        # marca o rádio do acordeão, e com ele o chip da fita: as regras
        # `body:has(#gc-pN:checked) .fita .chip:nth-child(n)` do gerador fazem
        # o destaque do topo seguir o acordeão. Um endereço, as duas metades.
        "alvo-aberto": _alvo_de_saida(ctx),
        # OS QUATRO AVISOS, TODOS EM LINHA DE RESSALVA (D-02). Eles vão em TODO
        # tique — vazio é `monta.NADA_A_DIZER`, que faz a linha sumir — porque a
        # chave que só aparece quando há o que dizer deixa na tela a tinta do
        # tique anterior. Um aviso que não sabe apagar é pior que o silêncio.
        #
        # **O `sem_driver` DE ANTES ERA EMISSÃO MORTA EM DOIS NÍVEIS**, e foi
        # SUBSTITUÍDO, não guardado ao lado: ele mandava
        # `st.get("controles_sem_driver")`, um `dict` que `pacotes.normalizar`
        # descarta antes da tela, para um endereço que página nenhuma tinha. O
        # dado é o mesmo; quem o vira frase é o dono
        # (`status_actions.texto_de_controle_nao_adotado`).
        "sem-driver": _frase_do_sem_driver(st),
        "radio-fragil": _frase_do_radio_fragil(st),
        "hub-em-comum": _frase_do_hub(),
        "gabinete-contagens": _frases_do_gabinete(),
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
        #
        # O `len(confissao)` DE 03/09/2026 são os campos da confissão do
        # desenho, e ele é LIDO em vez de digitado de propósito: são três com
        # lacuna, dois sem nada a confessar e ZERO sem censo. Um `+ 3` cravado
        # contaria pintura que não aconteceu nos dois últimos casos.
        # Os dois novos POR CONTROLE (`mic-caminho`, `luz-trava`) não precisam
        # de termo: eles entram pelo `sum(len(v) …)` das colunas.
        # O `+ 2` DE 04/09 são a tabela dos adaptadores e o escopo do botão do
        # microfone; o `+ len(veredito)` são a frase do veredito e os quatro
        # interruptores de estado dela, LIDOS em vez de digitados — o
        # dicionário vem vazio quando o produto não pôde responder, e contar um
        # `+ 5` cravado contaria pintura que não aconteceu. O
        # `len(vizinho_nome) * 3` virou `* 5`: o "onde" e a dica dele.
        # O `+ 4 + 5` DE 06/09/2026: as QUATRO linhas de ressalva (`sem-driver`,
        # `radio-fragil`, `hub-em-comum`, `gabinete-contagens`) e os CINCO
        # rádios do acordeão que o `alvo-aberto` marca. As quatro contam mesmo
        # caladas — `monta.NADA_A_DIZER` é uma escrita, e é ela que APAGA a
        # linha do tique anterior.
        "cobertura": {"pintados": 4 + 2 + 4 + 5 + len(confissao) + len(veredito)
                      + len(itens) * 4 + 1 + len(adap)
                      + len(vizinho_nome) * 5
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
    # `mic-escopo` SAIU DAQUI em 04/09/2026, e não porque alguém achou como
    # ligá-lo: porque **ele deixou de ser gesto**. A recusa que estava aqui
    # continua verdadeira palavra por palavra — `mic_button_toggles_system` é UM
    # por máquina (`daemon/lifecycle.py:301`, aplicado por
    # `ipc_draft_applier.py:592`) e a tela oferecia por controle, então ligá-lo
    # faria o segundo cartão sobrescrever a escolha do primeiro, calado.
    #
    # O QUE MUDOU FOI A PERGUNTA. A D-12 é dela: *"o botão é pra ligar o
    # microfone e ele ser ouvido no canal específico dele"* — UM ato só —, e
    # com o *"o botão do Controle sempre controla a interface"* de 30/08 não há
    # duas rotas com dois comportamentos a escolher. É a mesma doutrina que já
    # tirou desta aba a chavinha "pelo cabo / pelo rádio", com a razão escrita
    # na legenda: *"ela oferecia uma escolha que o transporte já tinha feito"*.
    # O `<select>` virou LEITURA (`escopo_do_botao_do_mic`), e a linha
    # `controle.*.mic.escopo` de `gui/aba_conexoes.SEM_FONTE` deixa de ser
    # espera dela — a palavra veio.
    #
    # A ENTRADA FICOU AQUI ATÉ A PUBLICAÇÃO, e saiu com ela no mesmo dia:
    # enquanto a página que ela usa ainda desenhava o `<select>`, tirá-la faria
    # o clique deixar de produzir **até a recusa** — a forma calada do mesmo
    # defeito. Conferido depois do `--publicar`: `data-gesto="mic-escopo"` não
    # existe mais nem na bancada nem na página publicada.
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
    em `controllers`, 0 = primário" (`ipc_handlers.py:4399`), e o próprio produto
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
    letras (`daemon/ipc_handlers.py:4500`): *"Com o alvo setado,
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
            f"{quem}: esta linha está vazia — a tela tem o lugar e há "
            f"{quantos} item(ns) aqui agora")
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
    (`ipc_handlers.py:6770`, QUATRO-MICROFONES-01): *"o 'Aplicar' tem de VALER
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
    `cfg.rumble is None` (`profiles/manager.py:2306`) e `"policy" not in
    model_fields_set` (`:2109`). O primeiro é o que o esquema chama de "campo
    não escrito = sem opinião", e é o que o merge POR CAMPO promete
    (`ControllerRumbleOverride`, docstring). O segundo existe para um override
    que fale só de outra coisa — e `custom_mult` sem `policy='custom'` a borda
    já recusa, então apagar a seção é a única forma limpa de dizer "sem
    opinião" aqui.

    IGUAL AO GLOBAL TAMBÉM APAGA, e a regra é do produto:
    `app/draft_config.with_controller_rumble:1193-1223` já decidiu que
    "intensidade igual à global não vira override". A razão é aritmética:
    `_controllers_to_rumble_scales` calcula `mult / base` e DESCARTA o fator
    1,0 (`profiles/manager.py:2329-2332`) — guardar o override só deixaria no
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


@gesto("08-conexoes.html", "teto-da-vibracao", grava="gravar_e_reaplicar")
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
    de um controle (`profiles/schema.py:768`), e a recusa diz em que aba
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


# ---------------------------------------------------------------------------
# DAR NOME A UM ADAPTADOR — o defeito da §3 desta aba, 04/09/2026
# ---------------------------------------------------------------------------
# O QUE ESTAVA AQUI ERA UMA PROMESSA VAZIA: a primeira célula da tabela "Rádio e
# adaptadores" nasce `contenteditable`, com uma dica dizendo *"dê um nome a
# este adaptador"*, e nenhum código da interface nova chamava
# `integrations/apelido_do_dongle`. **Ela digitava e perdia.**
#
# O MOTOR SEMPRE EXISTIU, e é o mesmo que a janela estável usa
# (`secao_mesa._ao_salvar_o_nome`): `renomear_o_dongle(endereco, nome)` grava o
# `Alias` no BlueZ por `busctl`, com a costura do prefixo Nintendo por cima
# quando o adaptador hospeda um Pro.

#: O NOME DO GESTO, e ele é UM só: o HTML o escreve, o teste o lê e o relatório
#: o cita. Digitá-lo três vezes é como um `data-gesto` fica órfão de um lado.
GESTO_DO_APELIDO = "renomear-adaptador"


def _endereco_e_nome_do_adaptador(caminho: str) -> tuple[str, str]:
    """Do `3-1.2` da tela para `(BD Address, o nome DELA de agora)`.

    A JUNÇÃO PASSA PELO `hciN` E NÃO SAI DAQUI, e a razão é do dono
    (`secao_mesa._dongle_por_interface`): *"o sysfs conhece porta e `vid:pid` e
    não publica o endereço; o BlueZ conhece o endereço e não conhece a porta"*.
    O índice inverte entre boots, então ele nasce e morre dentro desta chamada —
    o que atravessa para a escrita é sempre o BD Address.

    Devolve `("", "")` quando a mesa não responde ou o caminho não é de nenhum
    adaptador desta mesa. Um par vazio é uma RESPOSTA, e quem chama a transforma
    em recusa dizendo — nunca em escrita no adaptador errado.
    """
    if not caminho:
        return "", ""
    mesa = _mesa_do_radio()
    if mesa is None:
        return "", ""
    alvo = next((a for a in tuple(getattr(mesa, "adaptadores", ()) or ())
                 if str(getattr(a, "caminho", "") or "") == caminho), None)
    if alvo is None:
        return "", ""
    interface = str(getattr(alvo, "interface", "") or "")
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
            _dongle_por_interface,
        )

        dongle = _dongle_por_interface(_dongles()).get(interface)
        if dongle is not None:
            return str(dongle.endereco), str(dongle.nome)
    return "", ""


def _gravar_o_apelido(endereco: str, nome: str) -> Any:
    """Escreve o `Alias` no BlueZ. Devolve a `Renomeacao` do dono.

    NÃO CONFERE O QUE GRAVOU, e é do dono a razão medida: *"a escrita é
    assíncrona — ler logo depois devolve o valor antigo — e uma conferência com
    espera dentro travaria a interface por um segundo a cada salvamento."*

    A COSTURA DO PREFIXO NINTENDO VAI JUNTO, e ela é de `renomear_o_dongle`:
    num adaptador que hospeda um Pro, o alias sem o prefixo devolve o aparelho
    ao sniff frágil. Escrever o `Alias` cru daqui desfaria isso em silêncio.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.apelido_do_dongle import renomear_o_dongle

    return renomear_o_dongle(endereco, nome, dongles=_dongles())


@gesto("08-conexoes.html", GESTO_DO_APELIDO, grava="renomear_o_dongle")
def renomear_adaptador(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O nome que ELA deu ao adaptador, gravado no BlueZ.

    **O QUE CHEGA É `texto`**, e não `valor`: a célula é um `contenteditable`, e
    o ouvinte do piloto manda `texto: alvo.textContent` para quem não tem
    `value` (`hefesto_vivo.py`). `SEM_NOME` é o marcador do vazio na tela e
    NUNCA é gravado — ele é a ausência de nome, não um nome.

    **NÃO ESCREVE QUANDO O NOME NÃO MUDOU**, e a regra é da janela estável
    (`secao_mesa._ao_salvar_o_nome`): *"Sem ela, cada troca de aba reescreveria
    o alias dos três adaptadores com o valor que eles já têm — escrita à toa num
    barramento de sistema, e uma delas cairia bem em cima do prefixo que segura
    o Pro."* É também o que torna o clique da régua inofensivo: ela clica com o
    texto que a tela mostra, que é o nome de agora.

    **O QUE FALTA PARA ELE VALER NA MÃO DELA, e não é meu** — `hefesto_vivo.py`
    está no `nao_toca` desta sprint. O ouvinte do piloto escuta `click` e
    `change`; um `contenteditable` não dispara nenhum dos dois ao PERDER O FOCO,
    que é quando ela termina de digitar. O gesto está de pé e o endereço está no
    HTML; falta a linha do ouvinte. Ver o relatório desta frente.
    """
    caminho = str(o.get("caminho") or "").strip()
    if not caminho:
        raise ValueError(
            "renomear-adaptador: o clique não disse em qual adaptador — sem o "
            "caminho de barramento eu daria o seu nome ao rádio errado")
    novo = str(o.get("texto") or o.get("valor") or "").strip()
    if not novo or novo == SEM_NOME:
        raise ValueError(
            f"renomear-adaptador: {SEM_NOME!r} é como a tela mostra a ausência "
            f"de nome, e não um nome — apagar o apelido é outro gesto")
    endereco, agora = _endereco_e_nome_do_adaptador(caminho)
    if not endereco:
        raise RuntimeError(
            "renomear-adaptador: este adaptador não está mais ligado, ou o "
            "Bluetooth do sistema não respondeu por ele agora")
    if novo == agora:
        return
    feito = _gravar_o_apelido(endereco, novo)
    if not getattr(feito, "aplicado", False):
        # A FRASE DA RECUSA É DO MOTOR — `Renomeacao.porque` traz as três que ele
        # sabe dizer ("Este adaptador não está mais na mesa.", "Não achei este
        # adaptador no Bluetooth do sistema.", "O Bluetooth do sistema recusou o
        # nome novo."). Escrever uma quarta aqui seria a segunda grafia.
        raise RuntimeError(str(getattr(feito, "porque", "") or "")
                           or "o Bluetooth do sistema não gravou o nome novo")
    # O BLUEZ NÃO ECOA, então a próxima leitura tem de ser nova: sem isto a
    # tabela continuaria mostrando o nome velho até alguém apertar "Examinar".
    _dongles(recarregar=True)


@gesto("08-conexoes.html", "vizinho-o-que-e", grava="machine_declare")
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

    **E A SUGESTÃO DO KERNEL TAMBÉM VIRA `None`** — 03/09/2026. Desde que a
    primeira opção passou a carregar o que o kernel leu (`— Teclado? —`, ver
    :data:`_SUGESTAO_DO_KERNEL`), ela é escolhível como qualquer outra, e
    escolhê-la quer dizer *"continuo sem responder"*. Sem esta linha o clique
    cairia no `raise` abaixo, que nesta aba é recusa **calada** — a mesma forma
    dos quatro gestos que recusam sem uma palavra (`ValueError` não vai para a
    tela). E, mais grave: aceitá-la como resposta gravaria no `maquina.json` uma
    palavra que ela nunca disse, que é justamente o que a sugestão existe para
    não fazer.
    """
    posicao = _slot(o, len(_VIZINHOS), "vizinho-o-que-e")
    chave = _VIZINHOS[posicao]
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    para_id, _ = _tipos_de_radio()
    if rotulo in ("", _a_pergunta()) or rotulo in _perguntas_sugeridas():
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

    O CORPO SAIU DAQUI — 03/09/2026, `MIGRA-08-01`. Ele agora é
    :func:`_correr_o_exame_completo`, porque a ENTRADA na aba corre o mesmo
    exame (ver :func:`_pedir_o_exame_de_entrada`) e duas grafias do mesmo exame
    divergiriam no primeiro argumento novo.
    """
    _correr_o_exame_completo()


def _correr_o_exame_completo() -> None:
    """As CINCO conferências mais as ordens de serviço, sobre a máquina dela.

    **NÃO CABE NUM TIQUE**, e é a razão de existir separado do
    :func:`_conferencias`: `pareamentos` forka `busctl` (teto de 5 s) e
    `ler_a_mesa` proíbe tique no próprio docstring. Quem chama põe numa thread.

    Levanta quando o exame volta vazio: um exame que não achou nem uma linha
    não é "está tudo bem", é "não consegui olhar", e a diferença entre os dois
    é o que esta casa chama de *ausência de notícia lida como sucesso*.
    """
    global _EXTRAS, _QUANDO_O_EXAME
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import exame_da_mesa

    declaracao = _reler_a_declaracao()
    _dispensadas_do_disco(declaracao)
    _mesa_do_radio(recarregar=True)
    # E OS APELIDOS JUNTO — 04/09/2026. Eles vêm do BlueZ por `busctl`, logo
    # obedecem à mesma regra do `ler_a_mesa`: nunca em tique, e é o botão quem
    # renova. Sem esta linha, renomear um adaptador na tela deixaria a tabela e
    # a régua com o nome de antes até a próxima sessão.
    _dongles(recarregar=True)
    # E AS DUAS LEITURAS DO GABINETE JUNTO — 06/09/2026. Elas obedecem à mesma
    # regra do `ler_a_mesa` (varredura de `/sys` e leitura de disco, nunca em
    # tique), logo é este botão quem as renova. Sem estas duas linhas, espetar
    # um adaptador noutra entrada deixaria a linha do hub e as contagens do
    # gabinete com a leitura da abertura da janela — e a tela responderia sobre
    # o arranjo de antes com o carimbo "Examinado agora mesmo" ao lado.
    _entradas(recarregar=True)
    _gabinete(recarregar=True)

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


@gesto("08-conexoes.html", "ignorar", grava="machine_declare")
def ignorar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"⊘": cala ESTA ordem de serviço — e o MESMO botão a traz de volta.

    **É UM INTERRUPTOR DESDE 06/09/2026, decisão 08-Q5 dela:** *"A recomendação
    calada continua no lugar dela, em cinza, e o mesmo botão desfaz."* A trava
    que ela leu era esta: *"Hoje não há caminho de volta nenhum"* — medido com
    `grep` sobre as 4.400 linhas deste pacote, o único escritor de
    `ordens_dispensadas` era este gesto, e ele só sabia calar.

    | estado da linha | grava | memória |
    | --- | --- | --- |
    | falando | `{"quando": hoje, "arranjo": ordem.arranjo}` | `_DISPENSADAS[chave] = arranjo` |
    | calada | `{"quando": "", "arranjo": ""}` | `_DISPENSADAS[chave] = ""` |

    **DESFAZER É ESCREVER `arranjo=""`, e não remover a chave**: `machine.declare`
    não tem verbo de remoção (ver a nota de :data:`_DISPENSADAS`). O esquema
    aceita os dois vazios — `OrdemDispensada._so_a_data` só cobra a forma do que
    NÃO é vazio —, e um arranjo vazio guardado não casa com arranjo nenhum, logo
    a ordem volta a falar. O contorno é honesto: a marca fica no registro, e a
    REGRA é quem decide se ela cala.

    **O "DEU CERTO" DESTE CLIQUE É A PRÓPRIA LINHA MUDANDO DE COR**, e por isso
    ele não pede o pisca-verde de 1,5 s da 03-Q4: aquele existe para o gesto
    cuja resposta não se vê. Aqui a resposta É a tela.

    ---

    TEM DONO: `MesaDeclarada.ordens_dispensadas[chave] = {quando, arranjo}`
    (`utils/maquina.py`), o mesmo que `secao_exame._gravar_a_dispensa` escreve.

    **A CHAVE DA DISPENSA É O ARRANJO, NÃO A RECOMENDAÇÃO** — e é o que impede
    que este botão vire "grava e não cala". `ordens_da_mesa.ordens_novas`
    compara o arranjo GUARDADO com o de agora, e é isso que faz a dispensa valer
    para o FATO e não para a palavra: mudou o cabo, a ordem volta sozinha. Foi
    essa medição que manteve o ⊘ sem dono na primeira leva, e o que mudou não
    foi o esquema: é que agora existe `Item.ordem` na tela, porque o **Examinar
    Portas** traz o catálogo.

    UMA CONFERÊNCIA NÃO SE DISPENSA. As linhas `energia_do_radio`,
    `pareamentos`, `suporte_ao_controle`… respondem *"está certo?"*; só uma
    ORDEM responde *"faça isto"*, e só ela tem arranjo. O ⊘ numa conferência
    recusa dizendo — gravar ali criaria uma chave que regra nenhuma consulta.

    `quando` É SÓ A DATA. A hora não muda decisão nenhuma do produto e é um dado
    a mais sobre a rotina dela num arquivo que ela cola em relato de defeito —
    `OrdemDispensada._so_a_data` reprova qualquer outra forma.

    E A LINHA MUDA NA HORA: a decisão entra em `_DISPENSADAS` antes de o
    próximo tique montar a tira. Esperar o disco significaria a linha piscando
    meio segundo depois do clique dela.

    **A ORDEM DAS DUAS ESCRITAS NÃO SE INVERTE.** `_declarar` LEVANTA quando o
    daemon recusa, e a memória só muda depois. Inverter poria a tela num estado
    que o disco não tem — a linha cinza voltaria sozinha no tique seguinte, sem
    uma palavra, que é a definição de perder trabalho dela em silêncio.
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
    chave, arranjo = str(ordem.chave), str(ordem.arranjo)
    # O ESTADO SE PERGUNTA AO MESMO DONO QUE A TELA PERGUNTA — ver
    # :func:`_ordem_calada`.
    desfazendo = _ordem_calada(ordem)
    quando = "" if desfazendo else date.today().isoformat()
    guardar = "" if desfazendo else arranjo
    _declarar(p, {"ordens_dispensadas": {
        chave: {"quando": quando, "arranjo": guardar}}})
    _DISPENSADAS[chave] = guardar
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
# `_handle_machine_declare` (`daemon/ipc_handlers.py:6770`) → `maquina.json`, e
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


@gesto("08-conexoes.html", "escolher-entrada", grava="machine_declare")
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


@gesto("08-conexoes.html", "tirar-daqui", grava="machine_declare")
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


@gesto("08-conexoes.html", "nova-entrada", grava="machine_declare")
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


@gesto("08-conexoes.html", "nova-extensao", grava="machine_declare")
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


@gesto("08-conexoes.html", "nova-face", grava="machine_declare")
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
            "de todos.")
    # O MESMO BOTÃO É O CANCELAR — 06/09/2026, e o desenho já o prometia: o
    # `title` diz *"Enquanto ele espera o PS, o mesmo botão vira 'Cancelar'"*.
    # O RAMO VEM ANTES DE TUDO, e antes da guarda do transporte: durante a
    # espera o controle está FORA do rádio, então `ctx.por_uniq` não o encontra,
    # o transporte chega vazio e a guarda do cabo recusaria o próprio Cancelar
    # com a frase errada. Cancelar não fala com o BlueZ — não existe reconexão
    # neste produto, o botão PS é dela.
    if cancelar_a_espera(uniq):
        return
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
    # O CONTROLE CAIU — E É SÓ AQUI QUE A CONTAGEM COMEÇA. A condição é a do
    # dono (`_BlocoDaLuz._chegou_o_gesto`): `caiu` é falso tanto para "não achei
    # o controle no Bluetooth" quanto para "não consegui falar com o
    # `bluetoothd`", e nos dois casos mandar a pessoa apertar PS seria gastar o
    # gesto dela por uma coisa que não aconteceu.
    comecar_a_espera(uniq)


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
