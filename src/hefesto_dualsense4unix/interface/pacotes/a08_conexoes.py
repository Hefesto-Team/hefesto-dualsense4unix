#!/usr/bin/env python3
"""O pacote da aba `08` Conexões.

O QUE TEM DONO: a contagem da mesa por transporte, e é o que o cabeçalho desta
aba promete (`2 controles • 1 USB • 1 BT`). Sai de `controllers[]`, e a
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
import sys
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
#: O exame tem dono (`integrations/exame_da_mesa` devolve os itens prontos). A
#: chave `adaptadores` SAIU EM 23/09/2026 com a tabela que a lia
#: (TRANSPLANTE-DA-SECAO-01): quem está em qual adaptador vem agora do
#: `state_full` (`radio_ar`, `radio_governador`), que o daemon publica.
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


#: O que só o exame COMPLETO traz: `pareamentos`, `vizinhanca_das_portas` e as
#: ordens de serviço. Vazio até ela clicar em **Examinar Portas**.
_EXTRAS: tuple[object, ...] = ()

#: A ordem de serviço de cada POSIÇÃO da tira do exame, ou `None` quando aquela
#: linha é uma conferência (que não se dispensa).
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
#: A CONDIÇÃO SEM SUJEITO — 11/09/2026, A1-066. As duas frases que a citam têm
#: sujeitos de gêneros diferentes: aqui é a ORDEM (feminina) e no ⊘ é o
#: CONSELHO (masculino). Guardar a condição sozinha deixa cada uma concordar
#: com o seu sem que a frase seja digitada duas vezes.
VOLTA_QUANDO = "se você mudar os cabos"

ORDEM_IGNORADA_VOLTA = f"volta sozinha {VOLTA_QUANDO}"

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
DICA_DO_IGNORAR = ("Ignora este conselho. Ele fica em cinza na lista e volta "
                   f"sozinho {VOLTA_QUANDO}.")

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

# A SONDA DA MESA SUJA SAIU DESTA ABA — FRASES-E-DICAS-02, 13/09/2026. Ela
# alimentava só o aviso anexado à dica do botão da luz, e o aviso saiu da tela
# (`secao_controles`, a nota ao lado de `DICA_NO_CABO`). A varredura de
# `/proc/<pid>/fd` que ela pagava a cada dois segundos saiu do tique junto.


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
    """O microfone DESTE controle está ligado?

    **A REGRA INVERTEU EM 18/09/2026** (ordem dela: *"todos os controles tem
    que nascer com tudo mic, giroscopio e afins"*). Antes só `True` contava, e
    ausência era silêncio; agora só `False` desliga, e a ausência LIGA — que é
    o que o daemon faz desde a mesma data (`bt_mic.uniqs_recusados`).

    Continuam sendo DOIS estados na tela, não três: o que mudou é para que lado
    cai o controle sobre o qual ninguém disse nada. Ele agora cai para o lado
    do aparelho — um DualSense tem microfone.

    Erro de leitura responde `True` pela mesma razão que a fonte do daemon: com
    o default invertido, o lado seguro é não calar um microfone por engano.
    """
    try:
        chave = _so_hex(uniq)
        declarado = (declaracao.controles or {}).get(chave)
        return getattr(declarado, "microfone", None) is not False
    except Exception:
        return True


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


# A MARCA DE PROCEDÊNCIA E O `?` DO CARTÃO DA ORDEM SAÍRAM — FRASES-E-DICAS-02,
# 13/09/2026. Os dois moravam no cartão da ordem da coluna da direita: a marca
# `[derivado da conta]` na linha do ganho (decisão [04] do PO, 04/09) e o `?`
# com *O que eu vi aqui* e *Por que importa* ao lado do imperativo. O
# imperativo (`div.faca`) e o ganho (`div.ganho`) saíram da coluna visível, e o
# `?` que já traz o mesmo conteúdo é o da linha do exame à esquerda
# (:func:`_dica_da_linha`, endereço `exame-calada`). Ver :func:`_html_da_ordem`.


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
    """O card de UMA ordem na coluna da direita: só o de→para, quando há destino.

    SEGUNDA GRAFIA COM DATA DE MORTE — ver :func:`_dono_sabe_desenhar_a_ordem`.
    As classes são as do desenho dela (`.ordem`, `.receita`, `.caixa`, `.seta`),
    as mesmas que o dono emite; o que muda é que aqui a `Ordem` é lida pelos
    campos que ela TEM.

    **O IMPERATIVO E O GANHO SAÍRAM DA VISTA — FRASES-E-DICAS-02, 13/09/2026.**
    O card mostrava, sem clique, o imperativo da ordem (`div.faca`) e a linha
    `Ganho esperado:` (`div.ganho`), inclusive quando ela dizia que o ganho não
    foi medido. As duas são instrução e confissão sobre um estado, e a ordem
    dela de 13/09 deixa na tela só estado e ajuda. O conteúdo não se perdeu: o
    `?` da linha do exame à esquerda traz *Por que importa · Ganho esperado · O
    que fazer* (:func:`_dica_da_linha`).

    NOTA QUE CADUCOU NA MESMA DATA: aqui estava escrito *"O GANHO VAI SEMPRE,
    inclusive quando ele confessa que não foi medido"*, citando
    `secao_exame._card_da_ordem`. A citação não era palavra dela; a regra de
    13/09 é, e ela vence.

    A RECEITA SÓ APARECE COM DESTINO, e é o que o dono não faz: ele emite as
    duas caixas sempre, e com `destino` vazio a tela mostraria `—  →  —`. Nas
    DUAS ordens desta máquina o `destino` é `''` — a regra achou o problema e
    não achou entrada livre nomeável para onde mandar (`SEM_DESTINO`) —, e sem
    destino o card não existe: devolve `""`.

    O QUE VAI NA CAIXA DA ESQUERDA é o `alvo.caminho` — o endereço de barramento
    (`3-1.2`), que é *"a palavra comum entre este módulo, o censo e o mapa"*
    (`gui.aba_conexoes.html_dos_adaptadores`).
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui.aba_conexoes import TRACO, _e

    destino = str(getattr(ordem, "destino", "") or "")
    if not destino:
        return ""
    de = str(getattr(getattr(ordem, "alvo", None), "caminho", "") or TRACO)
    # O TÍTULO E A INSTRUÇÃO VOLTARAM, e é escolha dela — 26/09/2026, olhando o
    # desenho novo: *«o que é a área que marquei em vermelho?»*. Sem os dois o
    # de→para era um par de endereços soltos. O título é o nome que ela deu à
    # caixa; a instrução é a `acao` da ordem, que já nomeia o aparelho.
    acao = str(getattr(ordem, "acao", "") or "")  # (noqa-acento) campo da Ordem
    faca = f'<div class="faca">{_e(acao)}</div>' if acao else ""
    return ('<div class="ordem">'
            f'<div class="ordem-tit">{TITULO_DA_ORDEM}</div>{faca}'
            f'<div class="receita"><span class="caixa">{_e(de)}</span>'
            f'<span class="seta">→</span>'
            f'<span class="caixa alvo">{_e(destino)}</span></div></div>')


#: O nome da caixa da ordem de serviço — dela, 26/09/2026.
TITULO_DA_ORDEM = "Sugestão de conexão"


#: O TETO DO DESENHO — decisão **08-Q7**, 06/09/2026. Mora aqui porque o `+N`
#: é conta do PRODUTO e o número é do DESENHO: a coluna do exame tem CINCO
#: blocos. (A fileira dos vizinhos, que tinha QUATRO, saiu em 23/09/2026 com a
#: seção do rádio: os vizinhos viraram selos na régua do espectro, sem teto.)
#:
#: **LIDOS DE UM LUGAR SÓ, nunca digitados nos dois arquivos.** O `aba08.py`
#: importa este pacote (`_pacote08`) e emite os blocos por estes mesmos números;
#: um teto digitado no gerador e outro no pacote divergiria no dia em que a
#: coluna crescesse, e o `+N` passaria a contar o que cabe em vez do que sobra.
#:
#: **O PRIMEIRO DEIXOU DE SER TETO — 19/09/2026.** Ele continua valendo como o
#: número de blocos que o DESENHO emite (e o `_exigir` do gerador continua
#: exigindo que os dois números batam), mas não é mais o que CABE na tela: o
#: piloto clona o molde da linha e a coluna rola. A decisão é dela, e a razão
#: é estrutural — as conferências devolvem LISTAS, uma porta problemática por
#: item, e o exame não tem máximo. Todo número cravado aqui como teto seria o
#: mesmo defeito com outra data.
TETO_DO_EXAME = 5


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


def _o_que_nao_coube(itens: list[Any]) -> dict[str, str]:
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
        # O `+N` DO EXAME CALOU — 19/09/2026, e a decisão 08-Q7 não caiu: ela
        # foi ATENDIDA melhor. A frase dela era *"Quando sobra, a lista ganha
        # uma última linha curta"*, e desde hoje a lista NÃO SOBRA: o piloto
        # clona o molde da linha (`hefesto_vivo.BOOTSTRAP`, `data-hef-molde`) e
        # todo achado aparece — palavra dela, 19/09: *a lista rola, sem teto*.
        #
        # A CHAVE CONTINUA INDO EM TODO TIQUE, e é obrigatório: pará-la
        # deixaria na tela o `+N` do tique anterior se algum dia ela voltasse a
        # falar. É a mesma razão do `exame-calada`, escrita logo acima.
        #
        # `_sobraram` NÃO MORREU — os vizinhos continuam com teto (o desenho
        # tem quatro entradas e a fileira não rola), e é ele quem diz. O que
        # esta linha guarda é a metade do exame.
        "exame-mais": nada,
    }


def _html_da_ordem(vivos: list[Any] | None = None) -> str:
    """A coluna da direita inteira: o de→para da ordem, ou a frase de nada a mudar.

    **A COLUNA ENXUGOU EM 13/09/2026 — FRASES-E-DICAS-02, §D.** Até aqui ela
    desenhava três coisas, cada uma de uma decisão do PO de 04/09
    (`docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md`):

    * **[03]** o cartão de cura abaixo da ordem, com *"O que fazer: …"* à
      vista, sem clique;
    * **[04]** a marca de procedência na linha do ganho;
    * **[07]** o `+N` quando havia mais ordem aberta do que card.

    O cartão da ordem e o de cura eram instrução e confissão sobre um estado,
    visíveis sem clique, e a ordem dela de 13/09 tira isso da tela
    (`sprints/arquivados/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`). Nada se perdeu: o
    `?` de cada linha do exame à esquerda traz *Por que importa · Ganho
    esperado · O que fazer* (:func:`_dica_da_linha`). O que fica é ESTADO: o
    de→para quando a ordem tem destino, com o `+N` das ordens que não couberam,
    e a frase do dono quando não há ordem nenhuma.

    `vivos` É A MESMA LISTA QUE PINTOU A TIRA, e recebê-la é o que impede as duas
    metades da seção de discordarem sobre quantas ordens estão abertas. Sem ela —
    o padrão — só o card sai.

    COLUNA SEM CARD É `monta.NADA_A_DIZER`, e não `""`: o `escrever()` do piloto
    troca vazio por `—` antes de olhar o alvo, e a coluna ganharia um travessão
    solto. É o caso das duas ordens desta máquina, que não têm destino.

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

    ordem = _ordem_na_tela()
    if ordem is None:
        return str(_tela.html_da_ordem(None))
    card = _card_da_ordem(ordem)
    if not card:
        return str(_monta().NADA_A_DIZER)
    if vivos is None:
        return card
    # AS ORDENS ABERTAS QUE NÃO COUBERAM — decisão [07], e só quando há card:
    # um `+N` debaixo de uma coluna vazia contaria o que não coube num lugar que
    # não mostra nada.
    abertas = sum(1 for i in vivos if getattr(i, "ordem", None) is not None)
    return card + _sobraram(abertas, 1, "recomendação", "recomendações")


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

#: O RÓTULO DA LINHA DA CONTA — FRASES-E-DICAS-02, 13/09/2026. A linha abria com
#: a confissão em primeira pessoa (`mapa_da_mesa.CONFISSAO_ABERTURA`) e listava
#: os itens no `title`; a ordem dela de 13/09 tira confissão da tela. Fica o
#: ESTADO — a contagem, por extenso — e os itens continuam no `?` do topo da
#: tela do mapa (`aba08.CONFISSAO_EM_DICA`), que é ajuda. O gerador lê daqui.
ROTULO_DA_CONTA = "Sem conferir neste desenho:"


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
    janela do desenho redesenha a cada mudança. Aqui só a CONTA vai à tela, por
    extenso, depois de :data:`ROTULO_DA_CONTA`. **Os itens saíram do `title` em
    13/09/2026** (FRASES-E-DICAS-02): eram confissão em primeira pessoa numa
    dica flutuante, e continuam no `?` do topo da tela do mapa, que é ajuda.

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
    return {"confissao-nada": "",
            "confissao-conta": palavra_da_conta(len(itens))}


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
    "Duplo clique para dar um nome a este adaptador — «Sala», «Extra». "
    "O resto da tela passa a usá-lo."
)


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


def rotulo_curto_do_controle(c: Any) -> str:
    """«Cosmic Red • USB» — o rótulo da linha do Check-up, sem a marca e sem o jogador.

    A-08-O-CHECKUP-ABSORVE-A-GESTAO-01 (25/09/2026): o «Player N» virou o campo
    do dono («P N», ou o nome que ela escreveu), logo a linha não o repete. O
    plástico some quando ninguém o leu, como em :func:`rotulo_do_controle`.
    """
    nome = str(c.get("nome") or "")
    plastico = (f'{nome} <span class="pt">•</span> '
                if nome and nome != _cor_desconhecida() else "")
    return f'{plastico}{c.get("via") or ""}'


#: O SEPARADOR DO DESENHO. Ele é um `<span>` com classe, e não um `•` solto,
#: porque a folha dela pinta o ponto mais apagado que o texto em volta. As duas
#: funções que compõem frase para esta tela usam este mesmo — ver
#: :func:`rotulo_do_controle`, que já o escrevia.
_PONTO = ' <span class="pt">•</span> '


def html_da_conta(frase: str) -> str:
    """A frase da contagem, com o separador que o desenho dela usa.

    O DONO DA FRASE É `gui.aba_conexoes.texto_da_contagem` — *"2 controles • 1
    USB • 1 BT"* —, e ele escreve o `•` cru porque nasceu para um rótulo
    do GTK. Esta função é só a tradução para o HTML dela; nenhuma palavra e
    nenhum número nascem aqui.

    POR QUE O GERADOR TAMBÉM CHAMA ISTO (`aba08.py`): enquanto o desenho e o
    produto escreverem a mesma frase duas vezes, elas divergem sem que ninguém
    veja. É a mesma razão pela qual o gerador já importava
    :func:`rotulo_do_controle` deste módulo.
    """
    return frase.replace(" • ", _PONTO)


#: POR ONDE O MICROFONE DESTE CONTROLE CHEGA — as duas metades da frase, e elas
#: são as do desenho dela. A regra é o ponto final dela de 28/08: *"se tiver em
#: modo rádio, então o mic é modo rádio"* — não há chavinha, o caminho é
#: DERIVADO do transporte. Pelo CABO o DualSense expõe placa USB Audio própria e
#: o PipeWire a publica sozinho; pelo RÁDIO não existe placa nenhuma e o áudio
#: vem em Opus dentro do HID 0x31, trazido pela ponte do Hefesto.
#:
#: A PALAVRA DO TRANSPORTE É USB E BT DESDE 24/09/2026
#: (AS-FRASES-QUE-A-BANCADA-ACHOU-01). Era «pelo cabo»/«pelo rádio», de antes da
#: decisão dela de 21/09 (a I9 revogada). O dono da palavra é
#: `home_actions._PALAVRA_DO_TRANSPORTE`, que este módulo não importa no topo
#: (o gerador da 08 o chama sem o `structlog`): quem prende as duas grafias é
#: `tests/unit/test_as_frases_que_a_bancada_achou.py`, que pergunta ao dono.
_CAMINHO_DO_MIC = {"bt": ("pelo BT", "Pela ponte"),
                   "usb": ("pelo USB", "Placa do controle")}


def caminho_do_microfone(via: str) -> str:
    """*"pelo BT • Pela ponte"* ou *"pelo USB • Placa do controle"*.

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
#:
#: A PALAVRA DO TRANSPORTE SEGUE A DA LINHA (:data:`_CAMINHO_DO_MIC`) desde
#: 24/09/2026: a dica e a linha que ela explica diziam «pelo cabo» onde a linha
#: ao lado diz USB. «Turno de rádio» fica: ali o rádio é o recurso que a barra
#: «Rádio em uso» mede, não a palavra do transporte.
_DICA_DO_MIC = {
    "bt": (
        "O microfone deste controle chega <b>pelo BT</b>, pela ponte do "
        "Hefesto — o DualSense não tem canal de áudio Bluetooth próprio."
    ),
    "usb": (
        "O microfone deste controle chega <b>pelo USB</b>, pela placa de áudio "
        "do próprio aparelho."
    ),
}

#: O que se diz do custo quando ele não existe. Pelo cabo o microfone não passa
#: pelo rádio, então não há fatia a contar — e dizer "0 turnos" seria um número
#: onde não há conta.
_MIC_NAO_CUSTA_RADIO = "Pelo USB ele não custa turno de rádio nenhum."


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


def dica_da_luz(via: str) -> str:
    """A dica do botão "A luz não acende" — a do PRODUTO, e nunca vazia.

    **TRÊS COISAS QUE A TELA NÃO DIZIA, e só a primeira FICOU:**

    1. **por que o botão está apagado.** O `title` do desenho é congelado: o
       primeiro cartão diz *"Este controle está no cabo"* e o segundo diz o que
       o clique faz — e os dois continuam dizendo isso quando o controle troca
       de transporte. A cor já obedecia (`trava_da_luz`, 03/09); a frase, não.
       `secao_controles.dica_do_botao` decide as duas juntas, e é ela quem passa
       a escrever;
    2. **o AVISO DA MESA SUJA — que SAIU em 13/09/2026** (FRASES-E-DICAS-02).
       Ele era anexado à dica quando outro programa segurava nó de controle, e
       era aviso com instrução: a ordem dela de 13/09 tira frase de aviso da
       tela em toda forma, `title` incluído. A dica fica com o que o botão faz;
    3. **a RAZÃO de a cura ser oferecida — que SAIU em 13/09/2026**
       (FRASES-E-DICAS-03). `frase_do_nascimento` colava, depois do que o botão
       faz, o carimbo que o daemon põe na conexão (`SINAL-NO-NASCIMENTO-01`):
       *«▲ nasceu com 1 processo(s) segurando o nó do controle — …»*. Era estado
       dito como aviso, e a mesma ordem o tira da dica. A função e a frase de
       reserva saíram do dono; o carimbo `nascimento` continua no `state_full`,
       para o diagnóstico.

    **NENHUMA FRASE NASCE AQUI.** A dica é a do dono, pedida com os três campos
    que `trava_da_luz` já respondeu — a mesma junção que
    `secao_controles._BlocoDaLuz` faz do lado da janela GTK. A ordem
    de 13/09 que tirou o aviso e a razão está no índice da terceira lista,
    `docs/process/sprints/arquivados/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        dica_do_botao,
    )

    # `dica_do_botao` pergunta ao objeto três coisas (`adotado`, `no_cabo`,
    # `uniq`), e as três são as MESMAS que `trava_da_luz` já respondeu para a
    # cor. Um objeto anônimo com esses três campos é o que faz as duas metades
    # do botão — a cor e a frase — saírem da mesma pergunta em vez de duas.
    no_radio = trava_da_luz(via) == LUZ_LIVRE
    dados = _dataclasses.make_dataclass(
        "ControleDaLuz", ["adotado", "no_cabo", "uniq"])(True, not no_radio, "x")
    return dica_do_botao(dados)


# ---------------------------------------------------------------------------
# A ESPERA PELO PS — a contagem e o Cancelar
# ---------------------------------------------------------------------------
#
# O RECADO DO FIM SAIU DA TELA — TELA-CALADA-03, 13/09/2026. Até aqui a frase
# com que a espera acaba (`FRASE_NAO_CAIU`, `frase_nao_voltou`) SOBREVIVIA na
# linha de ressalva do cartão, pela razão do ELO-MUDO-01: sem ela "não voltou"
# viraria silêncio. A palavra dela vence essa razão — *"essas frases de status
# (…) não deveria estar aparecendo"*, *"em todas as abas da interface"*. A régua
# que fica é a da sprint: **a instrução do segundo tempo FICA** (o «▲ Aperte PS
# · procurando…» com a contagem, e o «Cancelar»), **o recibo do fim SAI**. O fim
# não some calado: vai ao diário da janela, com a frase do dono, uma vez só.
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
    """Uma espera pelo PS, com o relógio por fora.

    `espera` é o dono (:class:`secao_controles.EsperaPeloPS`). A frase do fim
    NÃO fica guardada para a tela desde 13/09/2026 — ver o cabeçalho desta
    seção: :meth:`correr` a leva ao diário no instante em que a espera acaba.
    """

    def __init__(self, espera: Any, agora: float) -> None:
        self.espera = espera
        #: O instante do último segundo já contado.
        self.desde = float(agora)

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
        porque = str(self.espera.porque or "") if self.espera.acabou else ""
        if porque:
            # UMA VEZ SÓ: o `return` do topo não deixa uma espera acabada chegar
            # aqui de novo. O Cancelar não tem frase (`porque` vazio) e não fala.
            print(f"[relato] {PAGINA} · luz-nao-acende: {porque}", file=sys.stderr)


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
    return True


def esperando(uniq: str) -> bool:
    """Este controle está no estado 2 do desenho AGORA?"""
    dele = _ESPERAS.get(norm_mac(uniq) or "")
    return dele is not None and dele.contando


def _correr_as_esperas(agora: float | None = None) -> None:
    """Um passo do relógio, UMA vez por tique, para todas as esperas vivas.

    A ESPERA QUE ACABOU SAI DO DEPÓSITO no mesmo passo — 13/09/2026. Ela ficava
    para guardar o recado do fim, e o parâmetro `presentes` existia para apagar
    esse recado quando o controle voltava ("não voltou" com o controle de volta
    na lista seria a tela afirmando o que já não é verdade). Sem recado na tela
    não há o que guardar nem o que apagar: a linha volta a :func:`_sem_valor` e
    o botão a «A luz não acende» no mesmo tique.
    """
    quando = _agora() if agora is None else agora
    for chave, dele in list(_ESPERAS.items()):
        dele.correr(quando)
        if not dele.contando and _ESPERAS.get(chave) is dele:
            _ESPERAS.pop(chave, None)


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

    Fora da espera devolve :func:`_sem_valor`, que faz a `.ressalva` SUMIR em
    vez de virar um `—` — **inclusive quando a espera acabou falando**. Até
    13/09/2026 este ramo devolvia o recado do fim; ele saiu da tela pela
    TELA-CALADA-03 e vai ao diário (:meth:`_EsperaNaTela.correr`).
    """
    dele = _ESPERAS.get(norm_mac(uniq) or "")
    if dele is None or not dele.contando:
        return _sem_valor()
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        FRASE_APERTE_PS,
        frase_da_procura,
    )

    return (f"▲ {html.escape(FRASE_APERTE_PS)} · "
            f"{html.escape(frase_da_procura(dele.espera.restantes))}")


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


#: `tinta_legivel` e `_TINTAS_DE_TEXTO` SAÍRAM EM 23/09/2026: escolhiam a tinta
#: do número DENTRO do bloco da régua de Desempenho, e a régua saiu com a seção
#: antiga (TRANSPLANTE-DA-SECAO-01). Na sala nova a cor do plástico pinta a
#: silhueta e a borda da linha; nenhum texto se lê em cima dela.


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


# ---------------------------------------------------------------------------
# A CONTA DE SLOTS POR ADAPTADOR — SAIU EM 23/09/2026
# ---------------------------------------------------------------------------
# `_conta_de_slots` respondia «cabe mais um?» numa linha de texto sob a régua
# de Desempenho, com as frases de `plano_de_radio` e as duas respostas honestas
# de `secao_orcamento`. As duas saíram com a seção antiga (TRANSPLANTE-DA-SECAO-01):
# a sala do desenho aprovado responde no cartão de cada adaptador («com som 1
# de 2»), e o que não cabe vira o pedido do governador (`radio_governador`).
# A cicatriz da B1 — *não saber e estar vazio são coisas diferentes* — continua
# de pé, no `"lido"` da cena (ver `html_da_sala`).

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
# A CONTA, remedida no disco dela em 17/09/2026 (VIBRA-ACESA-01). Aqui estava,
# de 01/09: *"os 33 perfis têm `rumble.policy = None` e ZERO têm
# `controllers[*].rumble`"*. As duas metades caducaram, e a feature desta seção
# é justamente o que as derrubou — ela passou a ser usada.
#
#   29 perfis em `~/.config/hefesto-dualsense4unix/profiles/`
#    6 com `rumble.policy` global escrita (`max`, `balanceado`)
#    5 perfis com override por controle — 9 ENTRADAS `controllers[*].rumble`
#    4 perfis com override de gatilho — 8 entradas `controllers[*].triggers`
#
# REMEDIDO EM 19/09/2026, e a conta SUBIU — ela continua usando a feature:
#    6 perfis com override por controle — 11 ENTRADAS `controllers[*].rumble`
#    5 perfis com override de gatilho   — 10 entradas `controllers[*].triggers`
#
# A conta de 17/09 fica porque é o que derrubou a de 01/09; esta é a de hoje.
# Quem remedir de novo acrescenta a sua e não apaga estas duas: a SEQUÊNCIA é
# que mostra que a feature está sendo usada, e é ela que sustenta a decisão.
#
# A UNIDADE ESTÁ DITA DE PROPÓSITO: perfil e ENTRADA são contas diferentes, e
# confundi-las foi o que fez o número "9 perfis" circular — são 9 controles
# dentro de 5 arquivos, porque um perfil guarda um override por peça.
#
# O QUE MUDA NA CONTA DE BAIXO: com 6 perfis opinando globalmente, a base de
# `_controllers_to_rumble_scales` nem sempre é o `_RUMBLE_POLICY_PADRAO =
# "balanceado"` (mult 1,0). No DON'T SCREAM dela, com o global em `max`
# (mult 1,5), um override `economia` publica `0.3 / 1.5 = 0.2` — e não os 0,3
# que a linha antiga fazia parecer fixo. O fator é RELATIVO ao global do perfil,
# que é o que `fator_da_unidade` sempre calculou; o exemplo é que supunha um
# global que hoje não é o único.
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
    (`profiles/schema.py:2027`), logo é o que está no disco; procurar por
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
    guarda uma das outras três.

    FATO SUBSTITUÍDO — 19/09/2026. Aqui estava: *"Medido em 01/09/2026: zero dos
    33 perfis dela têm `controllers[*].rumble`, então o caso é hoje
    inalcançável"*. **Deixou de ser verdade, e o próprio arquivo já dizia**: o
    bloco de :3183, remedido em 17/09 pela VIBRA-ACESA-01, conta 5 perfis com
    override por controle. Duas afirmações opostas no mesmo arquivo obrigam
    quem lê a escolher, que é o defeito que a regra do fato-substituído existe
    para matar.

    **Remedido no disco dela em 19/09/2026, e o número CRESCEU de novo:**

        29 perfis
         6 com override de rumble por controle  ·  11 entradas
         5 com override de gatilho              ·  10 entradas

    O caso **é alcançável hoje**, e por isso continua tendo de estar escrito —
    a razão da nota não mudou, só o fato que a sustentava.
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
# junto com ele: as regras `body:has(#gc-pN:checked) .fita .chip[data-pref="pN"]`
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
    é o NÚMERO do jogador desde 20/09/2026 (`mesa_viva._lugares_da_mesa`): com o
    P1 fora, o índice 0 é o P2, e o `pref` dele é `p2`. As duas divergem sempre
    que um lugar fica vazio ou o primário não é o de menor número — é a mesma
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


@registrar("08-conexoes.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    global _ORDENS_NA_TELA
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
    # desenho tem CINCO linhas de exame (`TETO_DO_EXAME`); se a mesa dela
    # render mais, a pintura escreve nos lugares que existem e o endereço
    # `exame-mais` diz quantos não couberam. Nenhum clique age sobre o alvo
    # errado (o `data-v` só vai até o teto e o `_slot` confere a faixa).
    #
    # **A DÍVIDA QUE ISTO FECHA ESTAVA ESCRITA AQUI**, e o comentário que a
    # descrevia — *"Aqui não há onde dizer ainda"* — foi substituído em vez de
    # guardado ao lado: o Hefesto não descreve a limitação, ele constrói o
    # mecanismo que a remove (10-Q6).

    declaracao = _declaracao()
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
    #                          (`profiles/manager.py:2943`)
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

    # UM PASSO DO RELÓGIO DA ESPERA, UMA VEZ POR TIQUE — ver a seção "A ESPERA
    # PELO PS". Ele vem antes do laço porque a espera é do RELÓGIO, não do
    # cartão: chamá-lo por controle entregaria N tiques por segundo ao dono numa
    # mesa de N, e a contagem correria mais rápido quanto mais cheia a mesa.
    #
    _correr_as_esperas()

    # O NOME DO DONO DE CADA CONTROLE, uma leitura por tique para a mesa
    # inteira (ver :func:`_nomes_dos_donos`).
    nomes = _nomes_dos_donos()
    colunas = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        teto_campo, teto_frase = _teto_do_controle(overrides, uniq, vibracao, sem_dono)
        eu = da_mesa.get(uniq) or {}
        colunas[uniq] = {
            "via": (c.get("transport") or "").upper(),
            # A BATERIA COMO A TELA A ESCREVE — `Controle.texto_da_bateria`, o
            # dono (em `gui.aba_conexoes`), que põe o TRAVESSÃO quando
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
            # O «Player N» SAIU DO RÓTULO em 25/09/2026: ele é o campo do dono
            # (`dono`), logo abaixo — ver :func:`rotulo_curto_do_controle`.
            "nome": rotulo_curto_do_controle(eu) if eu else "",
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
            # O aviso da mesa suja e a razão do carimbo de nascimento saíram da
            # dica em 13/09/2026 (ver a função): ela diz só o que o botão faz, e
            # o `nascimento` do `state_full` fica para o diagnóstico.
            "luz-dica": dica_da_luz(str(c.get("transport") or "")),
            # O RÓTULO DO BOTÃO, e é ele que cumpre a promessa do `title`: na
            # espera o mesmo botão diz "Cancelar". Ver :func:`texto_do_botao_da_luz`.
            "luz-texto": texto_do_botao_da_luz(uniq),
            # A LINHA DA ESPERA — o pedido do PS com a contagem enquanto ela
            # corre, e NADA depois (o recado do fim saiu da tela em 13/09/2026).
            # Fora da espera ela não ocupa nada (`monta.ressalva`). Ver
            # :func:`linha_da_espera`.
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
        # A LINHA DO CHECK-UP (A-08-O-CHECKUP-ABSORVE-A-GESTAO-01): os seis
        # selos do estado, o botão da economia e o nome do dono.
        colunas[uniq].update(estado_do_controle(c, eu, st, declaracao))
        colunas[uniq].update(campos_da_economia(declaracao, uniq))
        colunas[uniq]["dono"] = dono_na_linha(nomes, uniq, eu.get("jogador"))
    # UMA LEITURA SÓ, e ela é a razão de esta linha não estar dentro do
    # dicionário: a `cobertura` conta os campos da confissão, e chamar a função
    # duas vezes releria o barramento no mesmo tique.
    confissao = _confissao_do_mapa()
    # PELA MESMA RAZÃO DA CONFISSÃO: a `cobertura` conta os campos do veredito, e
    # chamar `_veredito_do_exame` duas vezes refaria a conta do cabeçalho no
    # mesmo tique.
    veredito = _veredito_do_exame(vivos)
    return {
        # A TELA DO MAPEAR (A-08-O-CHECKUP-ABSORVE-A-GESTAO-01): o que o dono do
        # mapa das portas vê agora — ver :func:`campos_do_mapear`.
        **campos_do_mapear(),
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
        # A RÉGUA DO RÁDIO, A CONTA DE SLOTS E A TABELA DOS ADAPTADORES SAÍRAM
        # em 23/09/2026 (TRANSPLANTE-DA-SECAO-01): a seção inteira é o
        # `mapa-do-radio.html` aprovado, e os campos dela vêm de
        # :func:`campos_do_radio`, no fim deste dicionário.
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
        **_o_que_nao_coube(itens),
        # A SEÇÃO RÁDIO E ADAPTADORES — o `mapa-do-radio.html` aprovado,
        # TRANSPLANTE-DA-SECAO-01. Ver :func:`campos_do_radio`.
        **campos_do_radio(ctx),
        # O CARIMBO do topo do Check-up — publicado no mesmo dia e pela mesma
        # decisão, e também já pintado.
        "examinado": _carimbo_do_exame(),
        # A RESPOSTA EM UMA LINHA — **S-09, D-16**. Ver :func:`_veredito_do_exame`.
        # O carimbo acima diz QUANDO; esta linha diz O QUÊ, e na cor do pior
        # achado. O dicionário pode vir VAZIO, e o vazio é resposta: sem exame
        # não há juízo, e um travessão numa linha de veredito seria a tela
        # afirmando um nada.
        **veredito,
        "exame": itens,
        "achados": len(itens),
        "graves": sum(1 for i in itens if i["grave"]),
        # QUAL CONTROLE A SAÍDA ESTÁ MIRANDO — ver :func:`_alvo_de_saida`. Ela
        # marca o rádio do acordeão, e com ele o chip da fita: as regras
        # `body:has(#gc-pN:checked) .fita .chip[data-pref="pN"]` do gerador fazem
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
        # O `+ len(veredito)` são a frase do veredito e os quatro interruptores
        # de estado dela, LIDOS em vez de digitados — o dicionário vem vazio
        # quando o produto não pôde responder. O `+ 2 + 5`: as DUAS linhas de
        # ressalva (`sem-driver`, `radio-fragil`) e os CINCO rádios do acordeão
        # que o `alvo-aberto` marca — as ressalvas contam mesmo caladas, porque
        # `monta.NADA_A_DIZER` é uma escrita. O `+ 12` são os campos da seção
        # do rádio (:func:`campos_da_secao`), e a cerimônia entra pelo `sum`.
        "cobertura": {"pintados": 2 + 1 + 2 + 5 + len(confissao) + len(veredito)
                      + len(itens) * 4 + 1 + 12
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

# O 🎙 DA LINHA DO CONTROLE É O GESTO DA ABA 02 — um ato, um dono (D-12). No
# topo do módulo, e não dentro do gesto, para a régua do que grava
# (`test_todo_gesto_que_grava_esta_protegido._portas`) descer por ele.
from .a02_controles import mudo as _o_mudo_da_aba_02  # noqa: E402

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
    # OS TRÊS CUSTOS SEM DONO DA SEÇÃO DO RÁDIO — TRANSPLANTE-DA-SECAO-01,
    # 23/09/2026. O desenho aprovado deixa ligar e desligar cada custo da linha
    # do controle; o microfone tem dono (`custo-mic`, o mesmo ato do 🎙) e
    # estes três não têm.
    "custo-som":
        "a ponte de som por rádio sobe quando o JOGO manda som ao controle "
        "(`radio_governador`), e não há interruptor por controle no produto: o "
        "único ato que a liga à mão é o «Ligar aqui» da janela do adaptador "
        "cheio. Um botão que desligasse a ponte brigaria com o jogo no tique "
        "seguinte.",
    "custo-vibracao":
        "mesma razão do `custo-som`: a vibração por rádio viaja na MESMA ponte "
        "(o 0x32 com o bloco 0x11), e quem a sobe é o jogo. Não há dono por "
        "controle para desligá-la.",
    "custo-luz":
        "a barra de luz não custa rádio que se meça — ela viaja no mesmo "
        "relatório de saída que o controle já manda. O desenho a mostra como "
        "custo e o produto não tem o que tirar da conta; o interruptor dela "
        "mora na aba Iluminação.",
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

    O efeito que ESTE gesto entrega é o do daemon, e ele é real. A FITA DO TOPO
    ACOMPANHA NO TIQUE SEGUINTE, e não é este gesto que a move: o destaque do
    chip vem do `:checked` do acordeão, que :func:`_alvo_de_saida` marca pelo
    alvo que o daemon guardou, e as regras do gerador acham o chip pelo número
    do jogador (`data-pref`, A-GESTAO-SEGUE-O-JOGADOR-01).
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("alvo: o clique não disse em qual controle")
    indice = _indice(ctx, uniq)
    if indice is None:
        raise RuntimeError(
            "Este controle não está na lista do serviço — sem ele, o alvo "
            "cairia noutro controle.")
    p.chamar("controller.target.set", index=indice)


@gesto("08-conexoes.html", "todos")
def todos(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"▴": volta ao broadcast — as ações voltam a valer para a mesa inteira.

    O `title` do botão é o contrato: *"Fecha. A fita volta para «Todos» e todos
    abrem juntos."* No daemon, "Todos" é `index: null`
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
    DECLARADA: `MesaDeclarada.altura_da_antena` (`utils/maquina.py:306`), que só
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

    O par da de cima: `MesaDeclarada.linha_de_visada` (`utils/maquina.py:307`),
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
        return ("Este controle não tem endereço fixo, e sem ele não há onde "
                "guardar a ponte do microfone.")


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
    (`utils/maquina.py:680`), decisão dela de 22/08/2026 (*"por controle"*).

    QUEM CONSOME, e é por isso que o clique vale AGORA: o
    `_handle_machine_declare` relê o disco, rebinda `daemon._maquina` e SOBE OU
    DESCE o subsystem `bt_mic` no mesmo pedido — a nota está no próprio handler
    (`ipc_handlers.py:7326`, QUATRO-MICROFONES-01): *"o 'Aplicar' tem de VALER
    agora"*. Sem essa parte, a escolha dela só valeria no próximo início do
    daemon.

    **DESLIGAR GRAVA `False` — MUDOU EM 18/09/2026, e a razão é a inversão.**
    Até aqui gravava `None`, e a regra era boa enquanto o default fosse o
    silêncio: *"nunca pedi" e "não quero" deixam a ponte no chão do mesmo
    jeito*. Com a ordem dela — *"todos os controles tem que nascer com tudo mic,
    giroscopio e afins"* — a ausência passou a LIGAR, e aí `None` deixou de ser
    um jeito de desligar: seria o botão que não desliga.

    O medo que a regra velha protegia continua real e agora tem outro nome: um
    `false` no disco é o **único** registro de que ela disse não, e é o que
    impede o produto de religar sozinho no próximo boot. Ver
    `bt_mic.uniqs_recusados`.

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
        p.machine_declare({"controles": {chave: {"microfone": bool(ligado)}}}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o que você declarou")
    _reler_a_declaracao()


def _chave_no_perfil(ctx: Contexto, uniq: str) -> str:
    """A chave deste controle em ``Profile.controllers`` — doze hexa, ou ``""``.

    DUAS RÉGUAS, E AS DUAS TÊM DE CONCORDAR. A do PERFIL é `norm_mac` do
    esquema (`profiles/schema.py:1904`), que canoniza `aa:bb:…` em `aabbcc…`; a
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
    `cfg.rumble is None` (`profiles/manager.py:3227`) e `"policy" not in
    model_fields_set` (`:2481`). O primeiro é o que o esquema chama de "campo
    não escrito = sem opinião", e é o que o merge POR CAMPO promete
    (`ControllerRumbleOverride`, docstring). O segundo existe para um override
    que fale só de outra coisa — e `custom_mult` sem `policy='custom'` a borda
    já recusa, então apagar a seção é a única forma limpa de dizer "sem
    opinião" aqui.

    IGUAL AO GLOBAL TAMBÉM APAGA, e a regra é do produto:
    `app/draft_config.with_controller_rumble:1193-1223` já decidiu que
    "intensidade igual à global não vira override". A razão é aritmética:
    `_controllers_to_rumble_scales` calcula `mult / base` e DESCARTA o fator
    1,0 (`profiles/manager.py:3159-3209`) — guardar o override só deixaria no
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
        # (`profiles/schema.py:850-861`). Construir com `policy=` obrigaria a
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
    de um controle (`profiles/schema.py:833`), e a recusa diz em que aba
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
            "Este controle não tem endereço fixo, e sem ele a força só dele "
            "não tem onde ser guardada — a escolha cairia noutro aparelho.")

    escolha = str(o.get("valor") or o.get("rotulo") or "").strip()
    # A LISTA É A DA TELA, nunca três literais: `politica_do_rotulo` a lê de
    # `opcoes_do_teto()`, que é a mesma que o gerador desenhou. Foi assim que o
    # `mic-existe` se protegeu de um rótulo traduzido.
    policy = _tela.politica_do_rotulo(escolha)

    nome = perfil.nome_do_ativo(ctx.state).strip()
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
# O NOME É DO LUGAR, desde 23/09/2026 (TRANSPLANTE-DA-SECAO-01, item 1): o
# escritor é UM, `entrada_a_entrada.dar_nome`, e é o mesmo da janela estável
# (`secao_mesa._ao_salvar_o_nome`). O `Alias` do BlueZ é a projeção desse nome.

#: O NOME DO GESTO, e ele é UM só: o HTML o escreve, o teste o lê e o relatório
#: o cita. Digitá-lo três vezes é como um `data-gesto` fica órfão de um lado.
#: Desde 23/09/2026 é o nome do desenho aprovado (`mapa-do-radio.html`), e o
#: gesto mora com os outros da seção, em :func:`adaptador_renomear`.
GESTO_DO_APELIDO = "adaptador-renomear"


@gesto("08-conexoes.html", "vizinho-o-que-e", grava="machine_declare")
def vizinho_o_que_e(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"— O que é? —": ela responde o que é aquele rádio vizinho.

    TEM DONO: `MesaDeclarada.radios[vid:pid].tipo` (`utils/maquina.py:308`), e
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
    chave = str(o.get("alvo") or "")
    vizinhos = {v["id"] for v in _CENA_NA_TELA.get("vizinhos", ())}
    if chave not in vizinhos:
        raise ValueError(f"vizinho-o-que-e: {chave!r} não é um rádio que está na tela")
    rotulo = str(o.get("valor") or "").strip()
    if not rotulo:
        # O TOQUE NO SELO SÓ ABRE as respostas; quem responde é o botão do painel.
        return {"armou": True}
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
    return None


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
            "Esta linha é uma conferência, não um conselho — não há o que "
            "dispensar. Só as mudanças recomendadas se calam.")
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
# `_handle_machine_declare` (`daemon/ipc_handlers.py:7326`) → `maquina.json`, e
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
            "O clique não disse qual aparelho — dois adaptadores iguais "
            "seriam o mesmo botão.")
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

    A RECUSA DO CABO É DO DESENHO, não minha: o `title` do botão apagado
    (`aba08.LUZ_NO_CABO`, repintado por `secao_controles.DICA_NO_CABO`) diz que
    ele só vale no BT. Derrubar um controle que está no cabo não o derruba — e um botão
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
            "Este controle está no cabo, e no cabo a barra de luz não depende "
            "de reconexão.")

    resultado = radio.desconectar(uniq)
    if not resultado.caiu:
        raise RuntimeError(resultado.porque)
    # O CONTROLE CAIU — E É SÓ AQUI QUE A CONTAGEM COMEÇA. A condição é a do
    # dono (`_BlocoDaLuz._chegou_o_gesto`): `caiu` é falso tanto para "não achei
    # o controle no Bluetooth" quanto para "não consegui falar com o
    # `bluetoothd`", e nos dois casos mandar a pessoa apertar PS seria gastar o
    # gesto dela por uma coisa que não aconteceu.
    comecar_a_espera(uniq)


# ---------------------------------------------------------------------------
# A SEÇÃO DO RÁDIO — o `mapa-do-radio.html` aprovado, TRANSPLANTE-DA-SECAO-01
# ---------------------------------------------------------------------------
# O DESENHO É O APROVADO EM 23/09 (`mockup/mapa-do-radio.html`), e a regra da
# casa vale inteira: o Python PINTA, a página só mexe na tela. Tudo o que o
# desenho calculava em JavaScript — Hz, pontes, canais, quem está colado em
# quem — sai daqui, dos donos; o JavaScript da página abre e fecha o que já
# veio pintado.
#
# UMA CENA, DOIS LEITORES. :func:`cena_do_radio` monta a cena da máquina dela;
# o gerador (`interface/aba08.py`) monta a do desenho com o CSV do mockup
# aprovado. Os dois passam pelas MESMAS funções de desenho, e é isso que faz a
# bancada e a tela dela serem a mesma forma.
#
# O QUE MUDA DE TIQUE A TIQUE NÃO ENTRA NO HTML DA SALA: os Hz vão em listas
# próprias (`hz-movimento`, `hz-voz`, `hz-pouco`), distribuídas pela ordem do
# DOM. Com eles dentro, a sala seria reescrita a cada tique e levaria junto o
# campo em que ela estivesse digitando.
import threading  # noqa: E402
from collections.abc import Callable  # noqa: E402

from hefesto_dualsense4unix.integrations.radio_da_mesa import (  # noqa: E402
    FATIAS_DA_PONTE,
    HZ_AUDIO_COM_MIC,
    HZ_DA_PONTE,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    N_MAX_PONTES,
)

#: Quantas pontes de som ou vibração um adaptador aguenta — o dono é
#: `radio_da_mesa.N_MAX_PONTES`. O desenho aprovado chama de
#: `PONTES_POR_ADAPTADOR`, e a régua de paridade trava os dois juntos.
PONTES_POR_ADAPTADOR = N_MAX_PONTES
#: O que uma ponte tira do ar do adaptador, por segundo: `FATIAS_DA_PONTE`
#: fatias por relatório, menos a do escravo, vezes `HZ_DA_PONTE`. É o
#: `MARGINAL_DA_PONTE = 187.5` do desenho aprovado.
MARGINAL_DA_PONTE = (FATIAS_DA_PONTE - 1) * HZ_DA_PONTE
#: Os 79 canais do Bluetooth clássico em 2,4 GHz.
CANAIS_DO_BT = 79
#: Abaixo disto o giroscópio passa de 8 ms entre leituras e o número fica
#: laranja. É o corte do desenho aprovado (`HZ_QUE_ENGASGA`), declarado lá como
#: «corte de desenho, não medido»; a bancada dela decide o de verdade.
HZ_QUE_ENGASGA = 125.0
#: As larguras da linha de um controle, na proporção do desenho aprovado e em
#: constantes do dono: o que o controle manda (2 fatias por relatório), o que o
#: microfone acrescenta, e a ponte (a fatia do escravo junto).
_LARGURA_DA_ENTRADA = round(2 * HZ_INPUT_SEM_MIC, 1)
_LARGURA_DO_MIC = round(2 * (HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC - HZ_INPUT_SEM_MIC), 1)
_LARGURA_DA_PONTE = round((FATIAS_DA_PONTE + 1) * HZ_DA_PONTE, 1)

#: As palavras da seção. Curtas, porque é a ordem dela de 23/09: *"tá muito
#: grande, verborrágico e confuso"*.  (noqa-acento: citação literal dela)
SEGURE = "Segure PS + Create"
DE_UM_NOME = "Dê um nome a este adaptador"
ONDE_FICA = "Onde fica?"
MARCA_VARRENDO = ("Outro programa está procurando aparelhos por aqui. "
                  "Controle novo vai para outro adaptador.")
USB3_AO_LADO = "Entrada USB 3.0: faz ruído no rádio. Prefira uma 2.0."
SEM_RADIO = "Sem rádio"
#: O traço do «não há» e da faixa de canais (o do desenho aprovado).
TRACO_CURTO = "\u2013"

#: Os ícones do desenho aprovado, pelo tipo do aparelho. O prefixo `rd-` é o
#: sprite desta seção, e não colide com nenhum `id` da aba.
ICONE_DO_APARELHO = {
    "teclado": "teclado", "mouse": "mouse", "caixa": "caixa",
    "fone": "fone", "webcam": "webcam", "outro": "radio",
}
ICONE_DO_RADIO = {
    "wifi": "wifi", "fone": "fone", "teclado": "teclado",
    "mouse": "mouse", "webcam": "webcam", "caixa_de_som": "caixa", "caixa": "caixa",
}
#: O TIPO PELO ``Icon`` QUE O PRÓPRIO BLUEZ DERIVA — da classe no rádio
#: clássico, da ``Appearance`` no de baixo consumo. É a única pista de um
#: aparelho LE, que não publica ``Class``: o «BT5.0 Keyboard» da lista dela de
#: 25/09 (passo b7) chegava sem classe e virava o desenho genérico. O que não
#: está aqui (celular, relógio, computador, outro controle) é o genérico — o
#: produto não tem desenho para ele, e não inventa um.
TIPO_PELO_ICONE = {
    "input-keyboard": "teclado", "input-mouse": "mouse", "input-tablet": "mouse",
    "audio-headset": "fone", "audio-headphones": "fone", "audio-card": "caixa",
    "camera-video": "webcam", "camera-photo": "webcam",
}
#: A palavra de cada tipo na frase do parear (o «outro» é «aparelho»).
PALAVRA_DO_TIPO = {"teclado": "teclado", "mouse": "mouse", "fone": "fone",
                   "caixa": "caixa de som", "webcam": "webcam", "outro": "aparelho"}
#: OS BOTÕES DE PAREAR DE CADA MODELO, pelo produto do ``Modalias`` (Sony,
#: ``054C``): o DualSense e o Edge seguram PS + Create; o DualShock 4, PS +
#: Share. Um controle que não está aqui não ganha gesto: o produto não pede o
#: que não sabe (a lista dela de 25/09, passo c3).
BOTOES_DE_PAREAR = {"0ce6": "PS + Create", "0df2": "PS + Create",
                    "05c4": "PS + Share", "09cc": "PS + Share"}
ICONE_DO_CUSTO = {"mic": "mic", "som": "som", "haptica": "vibra"}
NOME_DO_CUSTO = {"mic": "microfone", "som": "som", "haptica": "vibração"}
#: As cores de quem não tem plástico: cinzas do mesmo mundo, para que a cor
#: continue sendo a identidade dos controles (desenho aprovado, `COR_DO_TIPO`).
COR_DO_TIPO = {
    "teclado": "#8b8fa8", "mouse": "#6d7186", "webcam": "#a8a08c",
    "caixa": "#8c8299", "fone": "#7e9aa8", "outro": "#606062",
}
ARTIGO_DO_TIPO = {"caixa": "a", "webcam": "a"}
PASSAGEIROS = (("giro", "Giroscópio e acelerômetro"), ("touch", "Touchpad"),
               ("botoes", "Botões, sticks e gatilhos"))

#: O que se diz no sino, pelo `o_que` do diário. NADA DO DIÁRIO CHEGA CRU À
#: TELA: o motivo técnico fica no arquivo; aqui fica a palavra dela.
FRASE_DO_DIARIO = {
    "adaptador cheio": "Pediram som com o adaptador cheio",
    "fila parada": "O adaptador parou de enviar",
    "ponte subiu": "Som além do limite",
}
#: A frase da ponte root já nasce escrita para o sino (o campo `frase`); o
#: nome da porta entra pelo dono (`entrada_a_entrada.com_o_nome_dela`).
PAROU_DE_REINICIAR = "parou de reiniciar o adaptador"


def _x(texto: object) -> str:
    return html.escape("" if texto is None else str(texto), quote=True)


def _ic(nome: str, classe: str = "") -> str:
    extra = f" {classe}" if classe else ""
    return f'<svg class="i{extra}" aria-hidden="true"><use href="#rd-{nome}"/></svg>'


def _silhueta(ap: dict[str, Any], classe: str = "ds") -> str:
    """O DualSense na cor do plástico dele, pelo `color` (o sprite é `currentColor`).

    SEM O `data-colorway` DO DESENHO, e é medido: no `mapa-do-radio.html` a
    silhueta o carrega para a aba08 repintar as zonas, mas a folha das zonas
    (`svg[data-colorway] .z-casca`) não alcança o que mora atrás de um `<use>`
    — o seletor casa o SÍMBOLO no sprite, e o sprite desta seção nem tem as
    classes de zona. O atributo seria cor cravada sem efeito, e o portão da cor
    (`check_a_cor_vem_do_aparelho.py`) o acusa com razão.
    """
    cor = ap.get("cor") or "var(--texto-mudo)"
    return (f'<svg class="i {classe}" aria-hidden="true" style="color:{_x(cor)}">'
            f'<use href="#rd-ds"/></svg>')


def _maiuscula(frase: str) -> str:
    return frase[:1].upper() + frase[1:]


def _cor_de(ap: dict[str, Any]) -> str:
    return str(ap.get("cor") or COR_DO_TIPO.get(str(ap.get("tipo")), "var(--texto-mudo)"))


def _veu(cor: str, alfa: float) -> str:
    m = re.fullmatch(r"#?([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})", cor or "")
    if not m:
        return cor
    r, g, b = (int(p, 16) for p in m.groups())
    return f"rgba({r},{g},{b},{alfa})"


def _hz(valor: Any) -> str:
    """O Hz de agora, inteiro; vazio = não sei (o piloto põe o travessão)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return ""
    return f"{round(valor)} Hz"


#: O SEPARADOR DO NOME NA ABA CONEXÕES — o da decisão dela de 25/09, com a
#: grafia dela: «Vitória ● Cosmic Red ● P1».
SEPARADOR_DO_NOME = " \u25cf "


def nome_na_conexoes(ap: dict[str, Any]) -> str:
    """«Vitória ● Cosmic Red ● P1» — o formato do nome, SÓ na aba Conexões.

    Decisão dela, 25/09/2026, 22h50: ``Nome ● Modelo do plástico ● Pn``. O NOME
    é do CONTROLE (o ``Alias`` que ela deu, pelo endereço), o modelo é o
    plástico lido, e o NÚMERO é do daemon vivo — *«sincronizado com o daemon»*
    (a lista dela, passo a2). Sem nome, o padrão «Player N» (a decisão [02] da
    aba 01: apagar o nome volta a ele); sem plástico lido ou sem número, a
    parte sai — campo sem informação não mostra nada. Quem não é controle é só
    o nome. <!-- noqa-acento: citação literal dela -->
    """
    nome = str(ap.get("nome") or "") or str(ap.get("rotulo") or "")
    if ap.get("tipo") != "controle":
        return nome
    partes = [nome, str(ap.get("cor_nome") or "")]
    jogador = ap.get("jogador")
    if isinstance(jogador, int) and not isinstance(jogador, bool):
        partes.append(f"P{jogador}")
    return SEPARADOR_DO_NOME.join(p for p in partes if p)


def como_se_chama(ap: dict[str, Any]) -> str:
    """«<b>Vitória ● Cosmic Red ● P1</b>» — o controle pelo nome da aba Conexões.

    FATO SUBSTITUÍDO (25/09/2026): era «o <b>Cosmic Red</b> de <b>Vitória</b>»,
    a cor na frente. A decisão dela do formato do nome vale para a aba inteira,
    e a pergunta de mover é da aba. Quem não é controle continua com o artigo.
    """
    if ap.get("tipo") == "controle":
        return f"<b>{_x(nome_na_conexoes(ap))}</b>"
    nome = str(ap.get("nome") or "")
    artigo = ARTIGO_DO_TIPO.get(str(ap.get("tipo")), "o")
    return f"{artigo} <b>{_x(nome or ap.get('rotulo') or '')}</b>"


def _produto_do_modalias(modalias: object) -> str:
    """``bluetooth:v054Cp0CE6d0100`` → ``0ce6``; ``""`` quando não é Sony."""
    m = re.search(r"v054Cp([0-9A-F]{4})", str(modalias or ""), re.I)
    return m.group(1).lower() if m else ""


def gesto_de_parear(ap: dict[str, Any]) -> str:
    """«Segure PS + Create» — o gesto que ESTE aparelho pede, ou ``""``.

    CADA TIPO DIZ O PRÓPRIO GESTO, OU NÃO PEDE O QUE NÃO SABE (a lista dela de
    25/09, passo c3: mover um TECLADO pedia «segure PS + Create» e mostrava o
    DualSense). O controle que o daemon publica é DualSense — sem ``Modalias``,
    é ele; com, vale o modelo (:data:`BOTOES_DE_PAREAR`). Um teclado, um fone
    ou um controle de outra marca não têm gesto que o produto conheça, e a
    linha não inventa um: a pergunta antes de mover já disse o que fazer.
    """
    if ap.get("tipo") != "controle":
        return ""
    modelo = _produto_do_modalias(ap.get("modalias"))
    if not modelo and not ap.get("modalias"):
        return SEGURE
    botoes = BOTOES_DE_PAREAR.get(modelo, "")
    return f"Segure {botoes}" if botoes else ""


def _desenho_de(ap: dict[str, Any], classe: str = "ds") -> str:
    """O DualSense na cor dele, ou o ícone do tipo — nunca o DualSense de um teclado."""
    if ap.get("tipo") == "controle":
        return _silhueta(ap, classe)
    return (f'<svg class="i ico" aria-hidden="true" style="color:{_x(_cor_de(ap))}">'
            f'<use href="#rd-{ICONE_DO_APARELHO.get(str(ap.get("tipo")), "radio")}"/></svg>')


#: O adaptador sem porta — o da placa-mãe, que não pendura em entrada nenhuma.
DENTRO_DA_MAQUINA = "Dentro da máquina"


def como_se_chama_o_lugar(lug: dict[str, Any]) -> str:
    """«o <b>Sala</b>», «a <b>Entrada 4.4</b>» ou «o adaptador <b>dentro da
    máquina</b>» — o nome dela primeiro."""
    if lug.get("nome"):
        return f"o <b>{_x(lug['nome'])}</b>"
    entrada = str(lug.get("entrada") or "")
    if entrada == DENTRO_DA_MAQUINA:
        return f"o adaptador <b>{_x(entrada[0].lower() + entrada[1:])}</b>"
    return f"a <b>{_x(entrada)}</b>"


def _titulo_do_lugar(lug: dict[str, Any]) -> str:
    return str(lug.get("nome") or lug.get("entrada") or "")


def _moradores(cena: dict[str, Any], lid: str) -> list[dict[str, Any]]:
    return [a for a in cena.get("aparelhos", ()) if a.get("lugar") == lid]


def _pontes(cena: dict[str, Any], lid: str) -> list[dict[str, Any]]:
    """As pontes deste adaptador NA ORDEM DAS VAGAS — a «N de 2» de cada linha.

    QUEM PASSOU DO LIMITE TEM DONO, e é o governador: a vaga que subiu por
    «Ligar aqui» leva `alem_do_limite`, e as `n_max` primeiras na ordem em que
    CHEGARAM cabem (`governador_do_radio._recalcular_o_limite`). Numerar pela
    ordem de `controllers` era um segundo dono da mesma resposta: com o
    Cosmic Red na frente da lista e marcado pelo governador, a linha dele dizia
    «Som 1 de 2» com o botão de som laranja, e a de OUTRO controle dizia
    «Passou do limite» (achado na conferência da TRANSPLANTE-DA-SECAO-01).
    Por isso: as marcadas por último, e o resto na ordem de chegada que o
    governador publica; sem ela, a ordem da cena.
    """
    moradores = [a for a in _moradores(cena, lid)
                 if a.get("tipo") == "controle" and a.get("ponte")]
    return sorted(moradores, key=lambda a: (bool(a.get("alem")),
                                            a.get("ordem_da_vaga", len(moradores))))


def _ocupado(cena: dict[str, Any]) -> bool:
    """Um movimento esperando PS + Create segura «Mover» e «Conectar» (item 6)."""
    return bool(cena.get("ocupado"))


def _canais_de(cena: dict[str, Any], lid: str) -> int | None:
    faixas = [v for v in cena.get("evitados", ()) if v.get("lugar") == lid]
    if not faixas and not cena.get("canais_medidos", {}).get(lid, False):
        return None
    return CANAIS_DO_BT - sum(int(v["fim"]) - int(v["ini"]) for v in faixas)


# -- a linha de um aparelho -------------------------------------------------


def _e_pouco(hz: Any) -> bool:
    """Movimento abaixo do que o jogo sente como liso — a parte fica laranja."""
    return isinstance(hz, (int, float)) and not isinstance(hz, bool) and hz < HZ_QUE_ENGASGA


def _linha_do_controle(ap: dict[str, Any], cena: dict[str, Any], com_hz: bool) -> str:
    aid = _x(ap["id"])
    mic = bool(ap.get("mic"))
    ponte = ap.get("ponte")
    alem = bool(ap.get("alem"))
    mov_flex = HZ_INPUT_COM_MIC if mic else HZ_INPUT_SEM_MIC
    voz_flex = f"{HZ_AUDIO_COM_MIC} 1 0" if mic else "0 0 26px"
    manda = round(_LARGURA_DA_ENTRADA + (_LARGURA_DO_MIC if mic else 0), 1)
    passageiros = "".join(
        f'<span class="passageiro" role="img" title="{_x(rot)}: vem junto, não custa nada" '
        f'aria-label="{_x(rot)}: vem junto, não custa nada">{_ic(ic)}</span>'
        for ic, rot in PASSAGEIROS)
    voz = (f'<span class="hz" data-campo="hz-voz" data-alvo="{aid}">'
           f'{_x(_hz(ap.get("hz_voz"))) if com_hz else ""}</span>') if mic else ""
    pouco = " pouco" if com_hz and _e_pouco(ap.get("hz_mov")) else ""
    nome = _x(ap.get("nome") or ap.get("rotulo") or "")
    botoes_da_ponte = []
    for k in ("som", "haptica"):
        ligado = ponte == k
        flex = "1 1 0" if (ponte is None or ligado) else "0 0 34px"
        hz = f'<span class="hz">{_x(_hz(HZ_DA_PONTE))}</span>' if ligado else ""
        passou = " Passou do limite: pode engasgar." if (ligado and alem) else ""
        rotulo = _maiuscula(NOME_DO_CUSTO[k])
        gesto = "custo-som" if k == "som" else "custo-vibracao"
        botoes_da_ponte.append(
            f'<button class="vaga {k}{" alem" if ligado and alem else ""}" '
            f'aria-pressed="{str(ligado).lower()}" aria-label="{rotulo} de {nome}" '
            f'title="{rotulo}: {round(HZ_DA_PONTE)} por segundo. Pelo BT, som ou '
            f'vibração, um por vez.{passou}" style="flex:{flex}" '
            f'data-gesto="{gesto}" data-alvo="{aid}">{_ic(ICONE_DO_CUSTO[k])}{hz}</button>')
    return (
        '<div class="faixa-do-aparelho" style="width:100%">'
        f'<div class="fluxo manda" style="flex:{manda} 1 0" title="O que o controle manda">'
        f'{_ic("manda", "seta")}'
        f'<div class="vaga entrada fixa partida" style="flex:{manda} 0 0" '
        'title="O que o controle manda">'
        f'<span class="parte movimento{pouco}" data-campo="hz-pouco" data-hef-alvo="classe" '
        f'data-hef-classe="pouco" data-alvo="{aid}" style="flex:{mov_flex} 1 0" '
        'title="Movimento por segundo">'
        f'{_ic("sinal")}<span class="hz" data-campo="hz-movimento" data-alvo="{aid}">'
        f'{_x(_hz(ap.get("hz_mov"))) if com_hz else ""}</span>{passageiros}</span>'
        f'<button class="parte voz selo-mic" style="flex:{voz_flex}" '
        f'aria-pressed="{str(mic).lower()}" aria-label="Microfone de {nome}" '
        'title="Microfone: divide a fila com o movimento" '
        f'data-gesto="custo-mic" data-alvo="{aid}">{_ic("mic")}{voz}</button>'
        '</div></div>'
        f'<div class="fluxo recebe" style="flex:{_LARGURA_DA_PONTE} 1 0" '
        'title="O que o PC manda para o controle">'
        f'{_ic("recebe", "seta")}'
        f'<div class="ponte" style="flex:{_LARGURA_DA_PONTE} 0 0">'
        + "".join(botoes_da_ponte) + '</div>'
        f'<button class="selo-zero" aria-pressed="{str(bool(ap.get("luz", True))).lower()}" '
        f'aria-label="Barra de luz de {nome}" title="Barra de luz: não pesa no rádio" '
        f'data-gesto="custo-luz" data-alvo="{aid}">{_ic("lightbar")}</button>'
        '</div></div>')


def _vaga_de(ap: dict[str, Any], cena: dict[str, Any]) -> int:
    if ap.get("tipo") != "controle" or not ap.get("ponte"):
        return 0
    pontes = _pontes(cena, str(ap.get("lugar")))
    return pontes.index(ap) + 1 if ap in pontes else 0


def html_da_linha(ap: dict[str, Any], cena: dict[str, Any], com_hz: bool = False) -> str:
    """Uma linha da sala: desenho, nome, o que manda e recebe, qual vaga de ponte."""
    aid = _x(ap["id"])
    esperando = bool(ap.get("esperando"))
    arrasta = not ap.get("fixo") and not esperando and not _ocupado(cena)
    nome = str(ap.get("nome") or "")
    rotulo = str(ap.get("rotulo") or "")
    quem = "controle" if ap.get("tipo") == "controle" else str(ap.get("tipo"))
    le = _x(f"{nome_na_conexoes(ap) or rotulo}, {quem}")
    if arrasta:
        abre = (f'<div class="linha" data-id="{aid}" data-alvo="{aid}" draggable="true" '
                f'tabindex="0" role="button" aria-label="{le} — Enter para mudar de adaptador">')
    else:
        abre = (f'<div class="linha{" esperando" if esperando else ""}" data-id="{aid}" '
                f'data-alvo="{aid}" aria-label="{le}">')
    desenho = _desenho_de(ap)
    campo = (f'<input class="nome" value="{_x(nome)}" placeholder="{_x(rotulo)}" '
             'aria-label="Nome deste aparelho" title="Clique para renomear; arraste para mover" '
             f'draggable="true" data-gesto="aparelho-renomear" data-alvo="{aid}">')
    if ap.get("tipo") == "controle":
        # O FORMATO DA ABA CONEXÕES (decisão dela de 25/09): o campo guarda o
        # NOME, e o plástico e o número vêm depois dele, do daemon vivo. O
        # campo tem a largura do nome, para o resto encostar nele (a largura
        # segue o que ela digita pelo roteiro da página, como a do adaptador).
        resto = nome_na_conexoes({**ap, "nome": "", "rotulo": ""})
        largura = max(len(nome or rotulo) + 2, 6)
        campo = campo.replace('<input class="nome" ',
                              f'<input class="nome" style="width:{largura}ch" ', 1)
        campo = (f'<span class="quem">{campo}'
                 + (f'<span class="quem-resto">{_x(SEPARADOR_DO_NOME + resto)}</span>'
                    if resto else "") + "</span>")
    if esperando:
        gesto = gesto_de_parear(ap)
        dica = _x(re.sub(r"</?b>", "", _como_se_pareia(ap)))
        fala = f'<span class="segure">{_x(gesto)}</span>' if gesto else ""
        return (abre + desenho + campo + f'<div class="features" title="{dica}">{fala}'
                '</div><span class="conta-da-vaga">' + TRACO_CURTO + '</span></div>')
    if ap.get("tipo") == "controle":
        faixa = _linha_do_controle(ap, cena, com_hz)
    elif ap.get("tipo") == "webcam":
        return (abre + desenho + campo + f'<div class="features"><span class="sem-radio" '
                f'title="Não usa rádio; só ocupa porta">{SEM_RADIO}</span></div>'
                '<span class="conta-da-vaga zero" title="Não usa rádio">'
                + TRACO_CURTO + '</span></div>')
    else:
        # CAIXA E FONE NÃO GANHAM HZ ESTIMADO (R10: nada estimado na tela). O
        # desenho dividia um custo calculado por quatro; aqui fica a vaga, com a
        # cor e o ícone de quem a ocupa, e o número só volta quando houver medida.
        cor = _cor_de(ap)
        faixa = (f'<div class="faixa-do-aparelho" style="width:100%">'
                 f'<div class="vaga entrada fixa" style="flex:1 1 0;background:var(--panel);'
                 f'border-color:{_x(cor)};color:{_x(cor)}" '
                 f'title="{_x(_maiuscula(nome or rotulo))}: usa o rádio">'
                 f'{_ic(ICONE_DO_APARELHO.get(str(ap.get("tipo")), "radio"))}'
                 '</div></div>')
    vaga = _vaga_de(ap, cena)
    passou = vaga > PONTES_POR_ADAPTADOR
    titulo = ("Passou do limite" if passou else f"Som {vaga} de {PONTES_POR_ADAPTADOR}"
              ) if vaga else "Sem som"
    fatias = (f'<span class="conta-da-vaga{" alem" if passou else ""}" '
              f'data-alvo="{aid}" title="{titulo}">'
              + (f"{vaga} de {PONTES_POR_ADAPTADOR}" if vaga else TRACO_CURTO) + "</span>")
    return abre + desenho + campo + f'<div class="features">{faixa}</div>' + fatias + "</div>"


# -- o cartão de um adaptador -----------------------------------------------


def _marcas_de_onde(lug: dict[str, Any], cena: dict[str, Any]) -> str:
    partes = []
    if lug.get("face"):
        icone = "hub" if lug.get("hub") else "placa"
        face = _x(lug["face"])
        partes.append(f'<span class="marca {"hub" if lug.get("hub") else "direto"}" role="img" '
                      f'title="{face}" aria-label="{face}">{_ic(icone)}</span>'
                      f'<span>{_x(lug.get("entrada") or "")}</span>')
    if lug.get("varrendo"):
        partes.append(f'<span class="marca varrendo" role="img" title="{MARCA_VARRENDO}" '
                      f'aria-label="{MARCA_VARRENDO}">{_ic("varrendo")}</span>')
    if lug.get("junto"):
        dica = _x(_maiuscula(str(lug["junto"])) + ".")
        partes.append(f'<span class="marca junto" role="img" title="{dica}" '
                      f'aria-label="{dica}">{_ic("aviso")}</span>')
    if lug.get("usb3"):
        partes.append(f'<span class="marca usb3" role="img" title="{USB3_AO_LADO}" '
                      f'aria-label="{USB3_AO_LADO}">{_ic("aviso")}</span>')
    for ap in _moradores(cena, str(lug["id"])):
        if ap.get("esperando"):
            gesto = gesto_de_parear(ap)
            quem = nome_na_conexoes(ap) or PALAVRA_DO_TIPO.get(str(ap.get("tipo")), "controle")
            dica = (f"{gesto} no {quem} até a luz piscar." if gesto
                    else re.sub(r"</?b>", "", _como_se_pareia(ap)))
            partes.append(f'<span class="espera" '
                          f'data-alvo="{_x(ap["id"])}" title="{_x(dica)}">'
                          f'{_desenho_de(ap)}{_x(gesto)}</span>')
    if lug.get("conectando"):
        partes.append(f'<span class="espera" data-alvo="" '
                      f'title="Segure PS + Create no controle até a luz piscar.">'
                      f'{_silhueta({})}{SEGURE}</span>')
    if not lug.get("sabido", True):
        pass  # o BlueZ ainda não disse onde ele pendura: nem placa-mãe, nem «Onde fica?»
    elif not lug.get("lugar"):
        # O ADAPTADOR DA PLACA-MÃE não pendura em entrada: não há o que mapear.
        partes.append(f'<span>{_x(lug.get("entrada") or DENTRO_DA_MAQUINA)}</span>')
    elif not lug.get("face"):
        partes.append(f'<a class="ensina" href="#mapear-entrada-a-entrada" '
                      f'data-alvo="{_x(lug.get("lugar") or "")}" title="Mapear Entrada a Entrada">'
                      f'{_ic("uma-a-uma")}{ONDE_FICA}</a>')
    return '<span class="onde">' + "".join(partes) + "</span>"


def _conta_do_lugar(lug: dict[str, Any], cena: dict[str, Any]) -> str:
    n = len(_pontes(cena, str(lug["id"])))
    maximo = PONTES_POR_ADAPTADOR
    classe = "estourou" if n > maximo else ("apertado" if n == maximo else "")
    dica = f"Controles com som ou vibração: {n} de {maximo}" + (
        " — o som engasga" if n > maximo else "")
    partes = [f'<span class="quanto canais-do-lugar {classe}" '
              f'role="img" title="{dica}" aria-label="{dica}">{_ic("som")}{n}/{maximo}</span>']
    canais = _canais_de(cena, str(lug["id"]))
    if canais is not None:
        dica = (f"Usa os {CANAIS_DO_BT} canais" if canais == CANAIS_DO_BT else
                f"Evita {CANAIS_DO_BT - canais} dos {CANAIS_DO_BT} canais (vizinhos)")
        apertado = " apertado" if canais < CANAIS_DO_BT else ""
        partes.append(f'<span class="canais-do-lugar{apertado}" '
                      f'role="img" title="{dica}" aria-label="{dica}">'
                      f'{_ic("radio")}{canais}/{CANAIS_DO_BT}</span>')
    livres = maximo - n
    if livres >= 1:
        dica = "Cabe mais 1 com som" if livres == 1 else f"Cabem mais {livres} com som"
        miolo = _ic("mais") + "".join(_ic("ds", "ds") for _ in range(livres))
        classe = ""
    else:
        dica = "Passou do limite: o som engasga" if livres < 0 else "Cheio de som (sem som, cabe)"
        miolo = _ic("nao-cabe")
        classe = " passou" if livres < 0 else " nao-cabe"
    partes.append(f'<span class="sobra{classe}" role="img" title="{dica}" '
                  f'aria-label="{dica}">{miolo}</span>')
    return '<span class="lugar-conta">' + "".join(partes) + "</span>"


def _barra_do_lugar(lug: dict[str, Any], cena: dict[str, Any]) -> str:
    pontes = _pontes(cena, str(lug["id"]))
    maximo = PONTES_POR_ADAPTADOR
    escala = max(maximo, len(pontes))
    vagas = []
    for i in range(escala):
        ap = pontes[i] if i < len(pontes) else None
        classe = "vaga-ponte" + (" cheia" if ap else "") + (" alem" if i >= maximo else "") + (
            " reservada" if ap and ap.get("esperando") else "")
        if ap:
            cor = _cor_de(ap)
            borda = f";border-color:{_x(cor)}" if i < maximo else ""
            dica = (f'{nome_na_conexoes(ap)} · '
                    f'{NOME_DO_CUSTO[str(ap["ponte"])]}'
                    + (" · esperando" if ap.get("esperando") else "")
                    + (" · passou do limite" if i >= maximo else ""))
            vagas.append(f'<div class="{classe}" style="background:{_x(_veu(cor, .5))}{borda}" '
                         f'title="{_x(dica)}">{_ic(ICONE_DO_CUSTO[str(ap["ponte"])])}</div>')
        else:
            vagas.append(f'<div class="{classe}" title="Vaga livre"></div>')
    estourado = len(pontes) > maximo
    teto = ""
    if estourado:
        teto = (f'<div class="marca-do-teto" '
                f'style="left:calc({maximo / escala * 100:.4g}% - 1.5px)" '
                f'title="Limite: {maximo}"></div>')
    return ('<div class="barra-do-lugar">'
            f'<div class="trilho vagas{" estourado" if estourado else ""}" '
            f'data-alvo="{_x(lug["id"])}">' + "".join(vagas)
            + "</div>" + teto + "</div>")


def html_do_lugar(lug: dict[str, Any], cena: dict[str, Any], com_hz: bool = False) -> str:
    """O cartão de um adaptador: a linha de cima, e os aparelhos quando aberto."""
    lid = _x(lug["id"])
    pontes = _pontes(cena, str(lug["id"]))
    moradores = _moradores(cena, str(lug["id"]))
    aberto = cena.get("aberto") == lug["id"]
    classes = ["lugar"]
    if len(pontes) > PONTES_POR_ADAPTADOR:
        classes.append("cheio")
    if lug.get("conectando") or any(a.get("esperando") for a in moradores):
        classes.append("esperando")
    if aberto:
        classes.append("aberto")
    ver = ("Esconder" if aberto else "Ver") + " os aparelhos deste adaptador"
    nome = str(lug.get("nome") or "")
    largura = max(len(nome or DE_UM_NOME) + 2, 10)
    sino = ""
    quedas = lug.get("quedas") or []
    if quedas:
        dica = f"{len(quedas)} {'queda' if len(quedas) == 1 else 'quedas'} — ver quando"
        sino = (f'<button class="sino" title="{dica}" aria-label="{dica}" '
                f'data-gesto="adaptador-historico" data-alvo="{lid}">{_ic("aviso")}</button>')
    chegou = " ".join(sorted(_x(c) for c in lug.get("chegou") or ()))
    # A CAIXA ÚNICA NÃO TEM SETA, E VÁRIAS SE ARRASTAM — decisões dela, 25/09:
    # com um adaptador só a caixa fica aberta (a seta abriria e fecharia nada,
    # e botão que não muda nada é botão morto), e com mais de um ela segura a
    # linha de cima e arrasta para mudar a ordem (o roteiro da página grava).
    unica = len(cena.get("lugares") or ()) == 1
    seta = "" if unica else (
        f'<button class="abre-lugar" aria-expanded="{str(aberto).lower()}" title="{ver}" '
        f'aria-label="{ver}" data-gesto="abrir-adaptador" data-alvo="{lid}">'
        '<span aria-hidden="true">▶</span></button>')
    arrasta = "" if unica else ' draggable="true" title="Arraste para mudar a ordem"'
    topo = (
        f'<div class="lugar-topo"{arrasta}>' + seta
        + f'<input class="lugar-nome" value="{_x(nome)}" placeholder="{DE_UM_NOME}" '
        f'aria-label="Nome deste adaptador" style="width:{largura}ch" '
        f'data-gesto="adaptador-renomear" data-alvo="{lid}">'
        + _marcas_de_onde(lug, cena) + sino + _barra_do_lugar(lug, cena)
        + _conta_do_lugar(lug, cena) + "</div>")
    linhas = "".join(html_da_linha(ap, cena, com_hz) for ap in moradores)
    apagado = ' apagado" aria-disabled="true' if _ocupado(cena) else ""
    lampada = ""
    if cena.get("proposta") and cena["proposta"].get("destino") == lug["id"]:
        lampada = (f'<button class="lampada{apagado}" title="Quem funciona melhor aqui" '
                   f'aria-label="Quem funciona melhor aqui" data-gesto="sugerir-alocacao" '
                   f'data-alvo="{lid}">{_ic("lampada")}</button>')
    soltar = ("Arraste outro para cá" if moradores else "Arraste um aparelho para cá")
    corpo = (f'<div class="aparelhos" data-alvo="{lid}">{linhas}'
             f'<div class="soltar-fila"><button class="soltar{apagado}" '
             f'title="Trazer um aparelho para cá" data-gesto="trazer-para-ca" '
             f'data-alvo="{lid}">{_ic("soltar")}{soltar}</button>{lampada}</div></div>')
    return (f'<div class="{" ".join(classes)}" data-id="{lid}" data-alvo="{lid}" '
            f'data-chegou="{chegou}">' + topo + corpo + "</div>")


# -- as janelas que a página abre -------------------------------------------


def _como_se_pareia(ap: dict[str, Any]) -> str:
    """O que ela faz com a mão, pelo tipo — o gesto do modelo, ou o genérico.

    O «outro» é «o aparelho» (era «ponha o outro para parear»); o controle de
    modelo que o produto não conhece é «o controle», sem botões inventados.
    """
    gesto = gesto_de_parear(ap)
    if gesto:
        return f"Depois, segure <b>{_x(gesto.removeprefix('Segure '))}</b> até a luz piscar."
    tipo = str(ap.get("tipo"))
    palavra = "controle" if tipo == "controle" else PALAVRA_DO_TIPO.get(tipo, "aparelho")
    artigo = ARTIGO_DO_TIPO.get(tipo, "o")
    return f"Depois, ponha {artigo} {_x(palavra)} para parear."


def pergunta_de_mover(ap: dict[str, Any], destino: dict[str, Any], cena: dict[str, Any]) -> str:
    """A pergunta ANTES de mover (R7): só ele sai, e o que ela faz com a mão."""
    ela = ARTIGO_DO_TIPO.get(str(ap.get("tipo"))) == "a"
    cheio = (ap.get("tipo") == "controle" and ap.get("ponte")
             and len(_pontes(cena, str(destino["id"]))) >= PONTES_POR_ADAPTADOR)
    return (f"Mover {como_se_chama(ap)} para {como_se_chama_o_lugar(destino)}?<br>"
            f"Só {'ela' if ela else 'ele'} sai daqui. {_como_se_pareia(ap)}"
            + (" Lá o som pode engasgar." if cheio else ""))


def _moldes_de_pergunta(cena: dict[str, Any]) -> str:
    # A JANELA DO PEDIDO ABRE UMA VEZ (`pedidosVistos`, na página) e congela o
    # texto do primeiro tique: um lugar ainda sem porta sabida entraria nela
    # como «o adaptador dentro da máquina» — dos DOIS lados da pergunta. Quem
    # não foi descrito espera o tique em que o BlueZ responder.
    todos = {str(lug["id"]): lug for lug in cena.get("lugares", ())}
    lugares = {lid: lug for lid, lug in todos.items() if lug.get("sabido", True)}
    moldes = []
    for ap in cena.get("aparelhos", ()):
        if ap.get("fixo") or ap.get("esperando") or ap.get("tipo") == "webcam":
            continue
        for lid, destino in lugares.items():
            if lid == ap.get("lugar"):
                continue
            moldes.append(f'<template class="pergunta-molde" data-alvo="{_x(ap["id"])}" '
                          f'data-destino="{_x(lid)}" data-sim="Mover">'
                          f'{pergunta_de_mover(ap, destino, cena)}</template>')
    pedido = cena.get("pedido")
    if pedido:
        ap = next((a for a in cena.get("aparelhos", ()) if a["id"] == pedido.get("uniq")), None)
        origem = lugares.get(str(pedido.get("lugar")))
        vagas = [v for v in pedido.get("vagas") or () if v in lugares]
        cedo = any(v in todos and v not in lugares for v in pedido.get("vagas") or ())
        o_que = "a vibração" if pedido.get("tipo") in ("vibracao", "haptica") else "o som"
        if ap is not None and origem is not None and not cedo:
            chave = _x(f'{pedido.get("uniq")}|{pedido.get("lugar")}')
            if vagas:
                destino = lugares[vagas[0]]
                moldes.append(
                    f'<template class="pergunta-molde" data-pedido="{chave}" '
                    f'data-alvo="{_x(ap["id"])}" data-destino="{_x(destino["id"])}" '
                    f'data-sim="Mover e ligar" data-outro="Ligar aqui">'
                    f'{_maiuscula(como_se_chama_o_lugar(origem))} já tem {PONTES_POR_ADAPTADOR} '
                    f'controles com som ou vibração.<br>Mover {como_se_chama(ap)} para '
                    f'{como_se_chama_o_lugar(destino)} e ligar lá?</template>')
            else:
                moldes.append(
                    f'<template class="pergunta-molde" data-pedido="{chave}" '
                    f'data-alvo="{_x(ap["id"])}" data-destino="" data-sim="" data-outro="Ligar">'
                    f'Todas as entradas já têm {PONTES_POR_ADAPTADOR} controles com som ou '
                    f'vibração.<br>Ligar {o_que} mesmo assim? Pode engasgar.</template>')
    return "".join(moldes)


def _botoes(itens: list[tuple[str, str, str]]) -> str:
    """`(ícone, rótulo, atributos)` → a lista de botões de um painel."""
    return ('<div class="escolha">' + "".join(
        f'<button class="btn" {attrs}>{_ic(ic) if ic else ""}{_x(rot)}</button>'
        for ic, rot, attrs in itens) + "</div>")


def _moldes_de_painel(cena: dict[str, Any]) -> str:
    lugares = list(cena.get("lugares", ()))
    moldes = []
    movidos = [a for a in cena.get("aparelhos", ())
               if not a.get("fixo") and not a.get("esperando") and a.get("tipo") != "webcam"]
    for lug in lugares:
        lid = str(lug["id"])
        # O SINO: o que aconteceu com este adaptador, pela hora, mais novo primeiro.
        if lug.get("quedas"):
            linhas = "".join(
                f'<div class="queda">{_ic("aviso")}<span>{_x(_maiuscula(q["porque"]))}</span>'
                f'<span class="quando">{_x(q["quando"])}</span></div>'
                for q in lug["quedas"])
            if lug.get("quedas_desde"):
                linhas += (f'<div class="queda-desde">Quedas contadas desde '
                           f'{_x(lug["quedas_desde"])}</div>')
            moldes.append(f'<template class="painel-molde" data-painel="sino" '
                          f'data-alvo="{_x(lid)}" data-titulo="{_x(_titulo_do_lugar(lug))}">'
                          f'<div class="historico">{linhas}</div></template>')
        # QUEM VEM PARA CÁ: o arrastar de quem não arrasta.
        vem = [(("ds" if a.get("tipo") == "controle"
                 else ICONE_DO_APARELHO.get(str(a.get("tipo")), "radio")),
                nome_na_conexoes(a),
                f'data-aparelho="{_x(a["id"])}" data-destino="{_x(lid)}"')
               for a in movidos if a.get("lugar") != lid]
        titulo = ("Quem vem para " + (lug.get("nome") or ("a " + str(lug.get("entrada") or "")))
                  + "?") if vem else "Nada para trazer"
        moldes.append(f'<template class="painel-molde" data-painel="quem-vem" '
                      f'data-alvo="{_x(lid)}" data-titulo="{_x(titulo)}">'
                      f'{_botoes(vem) if vem else ""}</template>')
    # PARA ONDE VAI: o mesmo ato, pelo teclado.
    for ap in movidos:
        itens = [("hub" if d.get("hub") else "placa",
                  f'{_titulo_do_lugar(d)} · com som {len(_pontes(cena, str(d["id"])))} de '
                  f'{PONTES_POR_ADAPTADOR}',
                  f'data-aparelho="{_x(ap["id"])}" data-destino="{_x(d["id"])}"')
                 for d in lugares if d["id"] != ap.get("lugar")]
        titulo = f'Para onde vai {nome_na_conexoes(ap)}?'
        moldes.append(f'<template class="painel-molde" data-painel="para-onde" '
                      f'data-alvo="{_x(ap["id"])}" data-titulo="{_x(titulo)}">'
                      f'{_botoes(itens)}</template>')
    # O QUE É ESTE RÁDIO: as respostas do produto (`secao_mesa._TIPOS_DE_RADIO`,
    # pelo `_tipos_de_radio`). A resposta vai no `value` do botão, que é o que o
    # ouvinte do piloto manda como `valor` — um `data-valor` seria sobrescrito.
    _, rotulos = _tipos_de_radio()
    for viz in cena.get("vizinhos", ()):
        itens = [(ICONE_DO_RADIO.get(tipo, "radio"), rotulo,
                  f'data-gesto="vizinho-o-que-e" data-alvo="{_x(viz["id"])}" '
                  f'value="{_x(rotulo)}"')
                 for tipo, rotulo in rotulos.items()]
        moldes.append(f'<template class="painel-molde" data-painel="o-que-e" '
                      f'data-alvo="{_x(viz["id"])}" data-titulo="O que é este rádio?">'
                      f'{_botoes(itens)}</template>')
    # CONECTAR: o destino vem escolhido pela D8, e o que está perto.
    destino = cena.get("destino_do_conectar") or (lugares[0]["id"] if lugares else "")
    chips = "".join(
        f'<button class="op" aria-pressed="{str(lug["id"] == destino).lower()}" '
        f'title="Com som: {len(_pontes(cena, str(lug["id"])))} de {PONTES_POR_ADAPTADOR}" '
        f'data-gesto="escolher-adaptador" data-alvo="{_x(lug["id"])}">'
        f'{_x(_titulo_do_lugar(lug))}</button>' for lug in lugares)
    achados = "".join(
        '<div class="achado">'
        + (_ic("ds", "ds cheio") if a.get("tipo") == "controle"
           else _ic(ICONE_DO_APARELHO.get(str(a.get("tipo")), "radio"), "ico"))
        + f'<span class="nome">{_x(a.get("nome"))}</span>'
        + (f'<span class="forca" title="Sinal: mais perto de zero, mais perto">'
           f'{_x(a["forca"])} dBm</span>' if a.get("forca") is not None else "")
        + (f'<button class="btn" data-gesto="conectar-aparelho" data-alvo="{_x(a["id"])}">'
           'Conectar</button>' if a.get("conhecido") else
           f'<button class="btn" data-gesto="parear-aparelho" data-alvo="{_x(a["id"])}">'
           'Parear</button>')
        + "</div>" for a in cena.get("perto", ()))
    moldes.append(f'<template class="painel-molde" data-painel="conectar" data-alvo="" '
                  f'data-titulo="Procurando" data-pulso="1">'
                  f'<div class="conectar"><div class="escolha-lugar" role="group" '
                  f'aria-label="Em qual adaptador conectar">{chips}</div>'
                  f'<div class="achados">{achados}</div></div></template>')
    return "".join(moldes)


#: A frase da sala quando o BlueZ RESPONDEU e não há adaptador — a mesma da
#: tabela que a seção substituiu (TRANSPLANTE-DA-SECAO-01).
NENHUM_ADAPTADOR = "Nenhum adaptador Bluetooth encontrado."


def html_da_sala(cena: dict[str, Any], com_hz: bool = False) -> str:
    """Os cartões dos adaptadores, e só eles.

    A SALA TEM DE SER ESTÁVEL entre tiques: o piloto a troca inteira quando o
    texto muda, e trocá-la no meio de um nome sendo digitado ou de um arrasto
    derruba os dois. Por isso o que muda a cada tique — os Hz — pousa nas
    listas `hz-*`, e as janelas (que carregam o sinal de quem está perto)
    moram em `radio-moldes`. `com_hz` é do DESENHO, que não tem tique.
    """
    if not cena.get("lugares"):
        # NÃO TER LIDO NÃO É NÃO TER — a cicatriz da B1 (23/08/2026): com o
        # serviço mudo as barras diziam «Folgada», byte a byte a tela de um
        # rádio vazio. A frase só sai quando alguém RESPONDEU que não há; sem
        # resposta (o primeiro tique, o BlueZ que não falou) a sala não afirma
        # nada.
        if not cena.get("lido", True):
            return str(_monta().NADA_A_DIZER)
        return f'<div class="sala-vazia">{NENHUM_ADAPTADOR}</div>'
    return "".join(html_do_lugar(lug, cena, com_hz) for lug in cena["lugares"])


def html_dos_moldes(cena: dict[str, Any]) -> str:
    """As perguntas, os painéis e o balão prontos, em `<template>` — a página os abre.

    COM UM MOVIMENTO ESPERANDO, NENHUMA PERGUNTA DE MOVER NASCE (item 6 da
    leva): o arrasto, a lista e o balão ficam sem janela para abrir, e o botão
    cinza já diz que é para esperar. Um molde a mais levaria a um «Mover» que a
    central recusa — a recusa que a tela existe para não precisar dar.
    """
    if not cena.get("lugares"):
        return ""
    perguntas = "" if _ocupado(cena) else _moldes_de_pergunta(cena)
    return perguntas + _moldes_de_painel(cena) + _molde_do_balao(cena)


def _molde_do_balao(cena: dict[str, Any]) -> str:
    """A sugestão da central (`radio_central.proposta`), atrás da lâmpada do destino."""
    proposta = cena.get("proposta") or {}
    ap = next((a for a in cena.get("aparelhos", ()) if a["id"] == proposta.get("controle")), None)
    destino = next((lug for lug in cena.get("lugares", ())
                    if lug["id"] == proposta.get("destino") and lug.get("sabido", True)), None)
    if ap is None or destino is None or _ocupado(cena):
        return ""
    desenho = _silhueta(ap) if ap.get("tipo") == "controle" else ""
    return (f'<template class="balao-molde" data-controle="{_x(ap["id"])}" '
            f'data-destino="{_x(destino["id"])}"><div class="balao" '
            f'data-destino="{_x(destino["id"])}">{_ic("lampada")}{desenho}'
            f'<span>{_maiuscula(como_se_chama(ap))} funciona melhor '
            f'n{como_se_chama_o_lugar(destino)}</span>'
            f'<button class="ok" data-gesto="aceitar-sugestao" data-alvo="{_x(ap["id"])}">'
            'Mover</button></div></template>')


# -- quem está no ar ---------------------------------------------------------


def _faixas_livres(evitados: list[dict[str, Any]]) -> list[tuple[int, int]]:
    livres, c = [], 0
    for v in sorted(evitados, key=lambda v: int(v["ini"])):
        if int(v["ini"]) > c:
            livres.append((c, int(v["ini"])))
        c = max(c, int(v["fim"]))
    if c < CANAIS_DO_BT:
        livres.append((c, CANAIS_DO_BT))
    return livres


def _pct(valor: float) -> str:
    return f"{valor / CANAIS_DO_BT * 100:.4g}%"


def _custa(faixa: dict[str, Any], evitados: list[dict[str, Any]]) -> int:
    if faixa.get("forca") == "fora":
        return 0
    return sum(max(0, min(int(faixa["fim"]), int(v["fim"])) - max(int(faixa["ini"]), int(v["ini"])))
               for v in evitados)


def html_dos_canais(cena: dict[str, Any]) -> str:
    """A régua dos 79 canais: onde o Bluetooth salta, o que ele evita, e — só
    quando se sabe o canal — o vizinho provável."""
    lugares = {str(lug["id"]): lug for lug in cena.get("lugares", ())}
    evitados = list(cena.get("evitados", ()))
    partes = [f'<div class="salto" style="left:{_pct(a)};width:{_pct(b - a)}"></div>'
              for a, b in _faixas_livres(evitados)]
    for v in evitados:
        dono = lugares.get(str(v.get("lugar")))
        quem = (re.sub(r"</?b>", "", _maiuscula(como_se_chama_o_lugar(dono)))
                if dono and dono.get("sabido", True) else "O rádio")
        partes.append(f'<div class="evitado" style="left:{_pct(int(v["ini"]))};'
                      f'width:{_pct(int(v["fim"]) - int(v["ini"]))}" title="{_x(quem)} parou de '
                      f'saltar nos canais {v["ini"]} a {v["fim"]} — medido no próprio adaptador">'
                      '</div>')
    na_faixa = [e for e in cena.get("espectro", ()) if e.get("forca") != "fora"]
    pistas: list[list[dict[str, Any]]] = []
    pista_de: dict[str, int] = {}
    for e in sorted(na_faixa, key=lambda e: int(e["ini"])):
        for i, pista in enumerate(pistas):
            if all(int(e["ini"]) >= int(o["fim"]) or int(e["fim"]) <= int(o["ini"]) for o in pista):
                pista.append(e)
                pista_de[e["id"]] = i
                break
        else:
            if len(pistas) >= 2:
                pistas[1].append(e)
                pista_de[e["id"]] = 1
            else:
                pistas.append([e])
                pista_de[e["id"]] = len(pistas) - 1
    for e in na_faixa:
        sem_nome = not e.get("nome")
        custa = _custa(e, evitados)
        classe = f'faixa provavel {e.get("forca", "")}' + (" sem-nome" if sem_nome else "") + (
            f' pista-{pista_de[e["id"]]}' if len(pistas) > 1 else "") + (" custa" if custa else "")
        dica = (f'{e.get("nome") or "Rádio sem nome"} — canais {e["ini"]} a {e["fim"]} (provável)'
                + (f". Custa {custa} canais." if custa else "."))
        fala = dica + (" Toque para dizer o que é." if sem_nome else " Toque para trocar.")
        icone = "ajuda" if sem_nome else ICONE_DO_RADIO.get(str(e.get("tipo")), "radio")
        partes.append(f'<button class="{classe}" style="left:{_pct(int(e["ini"]))};'
                      f'width:{_pct(int(e["fim"]) - int(e["ini"]))}" title="{_x(dica)}" '
                      f'aria-label="{_x(fala)}" data-gesto="vizinho-o-que-e" '
                      f'data-alvo="{_x(e["id"])}">{_ic(icone)}'
                      f'<span class="ch"> {e["ini"]}{TRACO_CURTO}{e["fim"]}</span></button>')
    return "".join(partes)


def html_fora_da_faixa(cena: dict[str, Any]) -> str:
    """O que está no ar e não tem lugar na régua: quem está em 5 GHz, e os
    vizinhos cujo canal a máquina não diz (o produto não inventa a faixa)."""
    partes = []
    for e in cena.get("espectro", ()):
        if e.get("forca") != "fora":
            continue
        dica = _x(f'{e.get("nome") or "Este rádio"} em 5 GHz: fora desta faixa')
        partes.append(f'<span class="selo-fora" role="img" title="{dica}" aria-label="{dica}">'
                      f'{_ic(ICONE_DO_RADIO.get(str(e.get("tipo")), "radio"))} 5 GHz</span>')
    for viz in cena.get("vizinhos", ()):
        tipo = str(viz.get("tipo") or "")
        rotulo = str(viz.get("nome") or "")
        sugestao = str(viz.get("sugestao") or "")
        dica = (_x(f"{rotulo}: canal que o sistema não diz. Toque para trocar.") if tipo
                else _x(f"{sugestao}? Toque para dizer o que é.") if sugestao
                else "Rádio sem nome. Toque para dizer o que é.")
        # O TIPO QUE O KERNEL SUGERE JÁ TEM DESENHO (a lista dela, passo b7): o
        # teclado que o sistema reconhece mostra o teclado, ainda com a borda de
        # quem não foi confirmado (`sem-nome`); o que ninguém sabe fica com o
        # genérico do desenho aprovado.
        sugerido = str(viz.get("sugestao_tipo") or "")
        icone = (ICONE_DO_RADIO.get(tipo, "radio") if tipo
                 else ICONE_DO_RADIO.get(sugerido, "ajuda") if sugerido else "ajuda")
        partes.append(f'<button class="selo-fora vizinho{"" if tipo else " sem-nome"}" '
                      f'title="{dica}" aria-label="{dica}" data-gesto="vizinho-o-que-e" '
                      f'data-alvo="{_x(viz["id"])}">{_ic(icone)}</button>')
    return "".join(partes)


def _evitados_do_pior(cena: dict[str, Any]) -> int:
    contas = [_canais_de(cena, str(lug["id"])) for lug in cena.get("lugares", ())]
    medidos = [c for c in contas if c is not None]
    return max((CANAIS_DO_BT - c for c in medidos), default=0) if medidos else -1


def html_espectro_conta(cena: dict[str, Any]) -> str:
    evitados = _evitados_do_pior(cena)
    faixa = list(cena.get("espectro", ()))
    pior = max(faixa, key=lambda e: _custa(e, list(cena.get("evitados", ()))), default=None)
    pior_custa = _custa(pior, list(cena.get("evitados", ()))) if pior else 0
    sem_nome = (sum(1 for e in faixa if not e.get("nome"))
                + sum(1 for v in cena.get("vizinhos", ()) if not v.get("tipo")))
    partes = [f"{evitados}/{CANAIS_DO_BT} evitados" if evitados >= 0 else ""]
    if pior and pior_custa:
        partes.append(f'pior: {pior.get("nome") or "sem nome"}')
    if sem_nome:
        partes.append(f"{sem_nome} sem nome")
    return " · ".join(p for p in partes if p)


def html_meus_no_ar(cena: dict[str, Any]) -> str:
    no_ar = [a for a in cena.get("aparelhos", ()) if a.get("tipo") != "webcam"]
    if not no_ar:
        return ""
    tipos: list[str] = []
    for a in no_ar:
        if a["tipo"] not in tipos:
            tipos.append(str(a["tipo"]))
    icones = "".join(_ic("ds", "ds") if t == "controle"
                     else _ic(ICONE_DO_APARELHO.get(t, "radio")) for t in tipos)
    contas = [c for c in (_canais_de(cena, str(lug["id"])) for lug in cena.get("lugares", ()))
              if c is not None]
    restam = ("" if not contas else str(contas[0]) if min(contas) == max(contas)
              else f"{min(contas)}{TRACO_CURTO}{max(contas)}")
    dica = f"Seus {len(no_ar)} aparelhos Bluetooth saltam pelos {restam} canais livres" if restam \
        else f"Seus {len(no_ar)} aparelhos Bluetooth saltam pelos canais livres"
    return (f'<span class="no-ar-dentro" role="img" title="{_x(dica)}" aria-label="{_x(dica)}">'
            f'{icones}&nbsp;{len(no_ar)} no ar</span>')


# -- a vizinhança das portas -------------------------------------------------


def _numero_da_porta(caminho: str) -> tuple[str, int] | None:
    m = re.fullmatch(r"(.*)\.(\d+)", caminho) or re.fullmatch(r"(\d+)-(\d+)", caminho)
    return (m.group(1), int(m.group(2))) if m else None


def _ao_lado(a: dict[str, Any], b: dict[str, Any]) -> bool:
    x, y = _numero_da_porta(str(a["caminho"])), _numero_da_porta(str(b["caminho"]))
    return bool(x and y and x[0] == y[0] and abs(x[1] - y[1]) == 1)


def _o_que_ocupa(porta: dict[str, Any], cena: dict[str, Any]) -> dict[str, Any] | None:
    ocupa = porta.get("ocupa")
    if not ocupa:
        return None
    lug = next((lg for lg in cena.get("lugares", ()) if lg["id"] == ocupa), None)
    if lug:
        return {"tipo": "adaptador", "nome": _titulo_do_lugar(lug), "radio": True, "icone": "radio"}
    ap = next((a for a in cena.get("aparelhos", ()) if a["id"] == ocupa), None)
    if ap:
        return {"tipo": ap["tipo"], "nome": ap.get("nome") or ap.get("rotulo"),
                "radio": ap["tipo"] != "webcam",
                "icone": "ds" if ap["tipo"] == "controle"
                else ICONE_DO_APARELHO.get(str(ap["tipo"]), "radio"), "cor": _cor_de(ap)}
    viz = next((v for v in (*cena.get("espectro", ()), *cena.get("vizinhos", ()))
                if v["id"] == ocupa), None)
    if viz:
        return {"tipo": viz.get("tipo"), "nome": viz.get("nome"), "radio": True,
                "icone": ICONE_DO_RADIO.get(str(viz.get("tipo")), "radio")}
    return None


def como_esta_a_porta(porta: dict[str, Any], cena: dict[str, Any]) -> tuple[str, str]:
    """`(estado, porquê)` — as três regras do desenho aprovado, pela porta ao lado."""
    meu = _o_que_ocupa(porta, cena)
    vizinhas = [o for o in cena.get("portas", ()) if o["id"] != porta["id"] and _ao_lado(o, porta)]
    radios = [o for o in vizinhas if (_o_que_ocupa(o, cena) or {}).get("radio")]
    tres = [o for o in vizinhas if o.get("usb") == "3.0" and _o_que_ocupa(o, cena)]
    if meu and meu.get("radio"):
        if tres:
            return "ruim", "USB 3.0 ao lado"
        if radios:
            quem = [str((_o_que_ocupa(o, cena) or {}).get("nome") or "") for o in radios]
            return "atento", "colado em " + (", ".join(q for q in quem if q) or "outro rádio")
        return "bom", "nenhum rádio ao lado"
    if not meu:
        if porta.get("usb") == "3.0":
            return "neutro", "livre (USB 3.0: melhor para o que não é rádio)"
        if radios:
            return "atento", "livre, rádio ao lado"
        return "bom", "livre"
    return "neutro", "não usa rádio"


def html_das_portas(cena: dict[str, Any]) -> str:
    grupos: list[tuple[str, list[dict[str, Any]]]] = []
    for porta in cena.get("portas", ()):
        grupo = next((g for g in grupos if g[0] == porta.get("grupo")), None)
        if grupo is None:
            grupo = (str(porta.get("grupo") or ""), [])
            grupos.append(grupo)
        grupo[1].append(porta)
    saida = []
    for nome, portas in grupos:
        botoes = []
        for porta in portas:
            meu = _o_que_ocupa(porta, cena)
            estado, porque = como_esta_a_porta(porta, cena)
            desenho = ""
            if meu:
                cor = f' style="color:{_x(meu["cor"])}"' if meu.get("cor") else ""
                classe = "i ds" if meu["icone"] == "ds" else "i"
                desenho = (f'<svg class="{classe}" aria-hidden="true"{cor}>'
                           f'<use href="#rd-{meu["icone"]}"/></svg>')
            dica = _x(f'{porta.get("rotulo") or porta["caminho"]} · USB {porta.get("usb")} · '
                      f'{(meu.get("nome") or meu.get("tipo")) if meu else "livre"} — {porque}.')
            usb3 = " tres" if porta.get("usb") == "3.0" else ""  # (noqa-acento) classe do desenho
            botoes.append(f'<button class="porta {estado}{usb3}" '
                          f'data-grupo="{_x(nome)}" title="{dica}" aria-label="{dica}" '
                          f'data-gesto="examinar-portas" data-alvo="{_x(porta["id"])}">'
                          f'{desenho}</button>')
        saida.append(f'<div class="grupo-de-portas" title="{_x(nome)}" aria-label="{_x(nome)}">'
                     + "".join(botoes) + "</div>")
    return "".join(saida)


def html_da_conta_do_radio(cena: dict[str, Any]) -> str:
    if not cena.get("lugares") and not cena.get("lido", True):
        return str(_monta().NADA_A_DIZER)  # «0 adaptadores» sem resposta seria inventar
    controles = sum(1 for a in cena.get("aparelhos", ()) if a.get("tipo") == "controle")
    lugares = len(cena.get("lugares", ()))
    return (f"{controles} {'controle' if controles == 1 else 'controles'} · "
            f"{lugares} {'adaptador' if lugares == 1 else 'adaptadores'}")


def campos_da_secao(cena: dict[str, Any]) -> dict[str, Any]:
    """O que o pacote emite para a seção, NA ORDEM: a sala antes dos Hz, porque
    os Hz pousam nos elementos que a sala acabou de escrever."""
    controles = [a for lug in cena.get("lugares", ()) for a in _moradores(cena, str(lug["id"]))
                 if a.get("tipo") == "controle" and not a.get("esperando")]
    com_mic = [a for a in controles if a.get("mic")]
    return {
        "conta-de-adaptadores": html_da_conta_do_radio(cena),
        "radio-sala": html_da_sala(cena),
        "radio-moldes": html_dos_moldes(cena),
        "hz-movimento": [_hz(a.get("hz_mov")) for a in controles],
        "hz-pouco": ["sim" if _e_pouco(a.get("hz_mov")) else "" for a in controles],
        "hz-voz": [_hz(a.get("hz_voz")) for a in com_mic],
        "espectro-canais": html_dos_canais(cena),
        "espectro-fora-da-faixa": html_fora_da_faixa(cena),
        "meus-no-ar": html_meus_no_ar(cena),
        "espectro-conta": html_espectro_conta(cena),
        "vizinhanca-das-portas": html_das_portas(cena),
        "radio-ocupado": "sim" if _ocupado(cena) else "",
    }


# -- a cena da máquina dela --------------------------------------------------
# O TIQUE RODA NO LAÇO DO GTK (o `pacote()` é chamado ali), e uma leitura lenta
# aqui congelaria a janela — a lição de 15/09. Por isso o que não vem no
# `state_full` (o BlueZ, o diário, o `kernel.log`, o `maquina.json`) é lido num
# fio próprio, e o tique pinta a última leitura pronta.

_FUNDO: dict[str, tuple[float, Any]] = {}
_FUNDO_EM_VOO: set[str] = set()
_TRAVA_DO_FUNDO = threading.Lock()
#: Quantas vezes cada leitura foi dada por velha (`_esquecer`). A leitura que
#: começou antes de um gesto gravar volta com o disco de ANTES, e é por este
#: número que ela sabe que já nasceu velha.
_GERACAO: dict[str, int] = {}
#: A régua liga isto para ler na hora, sem fio — e sem máquina dela.
LER_NA_HORA = False
#: O carimbo de quem venceu: `agora - VENCIDA` nunca cabe na validade.
VENCIDA = float("-inf")


def _em_fundo(chave: str, ler: Callable[[], Any], validade_s: float) -> Any:
    """A última leitura de `chave`; pede outra num fio quando ela venceu."""
    agora = time.monotonic()
    with _TRAVA_DO_FUNDO:
        visto = _FUNDO.get(chave)
        if (visto is not None and agora - visto[0] < validade_s) or chave in _FUNDO_EM_VOO:
            return None if visto is None else visto[1]
        _FUNDO_EM_VOO.add(chave)
        geracao = _GERACAO.get(chave, 0)

    def trabalhar() -> None:
        try:
            valor = ler()
        except Exception:  # a leitura nunca derruba a tela: sem ela, «não sei»
            valor = None
        with _TRAVA_DO_FUNDO:
            fresca = _GERACAO.get(chave, 0) == geracao
            _FUNDO[chave] = (time.monotonic() if fresca else VENCIDA, valor)
            _FUNDO_EM_VOO.discard(chave)

    if LER_NA_HORA:
        trabalhar()
        return _FUNDO[chave][1]
    threading.Thread(target=trabalhar, name=f"radio-{chave}", daemon=True).start()
    return None if visto is None else visto[1]


def _esquecer(*chaves: str) -> None:
    """Depois de um gesto que grava, a próxima volta lê de novo.

    A LEITURA DE AGORA FICA ATÉ A NOVA CHEGAR — achado na conferência da
    TRANSPLANTE-DA-SECAO-01. Esta função APAGAVA a chave, e o tique logo
    depois do gesto pintava «não sei» com o fio ainda lendo: o nome que ela
    acabara de dar sumia do campo (o `maquina.json` em branco), e depois de um
    renomear de aparelho a sala INTEIRA virava o vazio calado quando o daemon
    não publicava `radio_ar` — medido, um tique de sala apagada e de volta.
    Agora a leitura só VENCE: o tique seguinte pede outra e pinta a de antes,
    e a sala muda uma vez, para o que ela gravou.

    E A LEITURA QUE JÁ ESTAVA EM VOO nasce vencida (`_GERACAO`): ela pode ter
    lido o disco antes da gravação, e guardá-la com carimbo novo mostraria o
    nome velho pela validade inteira.
    """
    with _TRAVA_DO_FUNDO:
        for chave in chaves:
            _GERACAO[chave] = _GERACAO.get(chave, 0) + 1
            visto = _FUNDO.get(chave)
            if visto is not None:
                _FUNDO[chave] = (VENCIDA, visto[1])


def _ler_o_bluez() -> tuple[tuple[Any, ...], tuple[Any, ...]] | None:
    """`(adaptadores, aparelhos)` do dono do BlueZ. Sob a suíte, nada: a régua injeta."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import bluez_dbus

    if bluez_dbus.a_suite_esta_rodando():
        return None
    dono = bluez_dbus.dono()
    adaptadores = dono.adaptadores()
    aparelhos = dono.aparelhos()
    if adaptadores is None:
        return None
    return tuple(adaptadores), tuple(aparelhos or ())


def _ler_a_maquina() -> tuple[Any, dict[int, str]]:
    """O `maquina.json` e os barramentos DESTE boot — os dois que o nome da porta pede."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.mesa_de_radio import controladores_dos_barramentos
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    return carregar_maquina(), dict(controladores_dos_barramentos())


def _ler_o_historico() -> dict[str, Any]:
    """O que o sino lê: as quedas do `kernel.log`, desde quando se mede, e o diário."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import diario_do_radio, storm_doctor

    contagens = storm_doctor.historico_do_radio()
    try:
        linhas = storm_doctor.caminho_do_kernel_log().read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        linhas = []
    diario = diario_do_radio.ler()
    quedas = sorted(storm_doctor.quedas(storm_doctor.ler_eventos_do_radio(linhas)),
                    key=lambda e: e.carimbo)
    familia = contagens.get(storm_doctor.FAMILIA_DA_QUEDA)
    return {
        "desde": familia.medida_desde if familia is not None else "",
        "quedas": [(q, storm_doctor.o_fato_da_queda(q, diario),
                    diario_do_radio.pontes_de_pe(diario, q.carimbo)) for q in quedas],
        "diario": diario,
    }


def _dicionario(valor: object) -> dict[str, Any]:
    return valor if isinstance(valor, dict) else {}


def _mac(valor: object) -> str:
    return str(norm_mac(str(valor or "")) or "").upper()


def _hora(carimbo: float, hoje: float) -> str:
    local = time.localtime(carimbo)
    if time.strftime("%Y%m%d", local) == time.strftime("%Y%m%d", time.localtime(hoje)):
        return time.strftime("%H:%M", local)
    return time.strftime("%d/%m %H:%M", local)


def _quedas_por_adaptador(historico: dict[str, Any] | None, caminhos: dict[str, str],
                          maquina: Any, controladores: dict[int, str],
                          ) -> dict[str, list[dict[str, Any]]]:
    """`{endereço: [{quando, porque, carimbo}]}` — o sino de cada adaptador, pela hora.

    A queda do `kernel.log` não diz o adaptador: ela vai para o que tinha mais
    pontes de pé naquele instante (o mesmo que o fato conta). Do diário, só as
    quatro frases que a tela sabe dizer — o motivo técnico fica no arquivo.
    """
    if not historico:
        return {}
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import entrada_a_entrada

    agora = time.time()
    por: dict[str, list[dict[str, Any]]] = {}

    def pousar(endereco: str, carimbo: float, porque: str) -> None:
        if endereco and porque:
            por.setdefault(endereco, []).append(
                {"carimbo": carimbo, "quando": _hora(carimbo, agora), "porque": porque})

    for queda, fato, de_pe in historico.get("quedas") or ():
        cheio = max(de_pe.items(), key=lambda par: len(par[1]), default=("", set()))[0]
        pousar(_mac(cheio), float(queda.carimbo), fato or "Os controles caíram")
    for linha in historico.get("diario") or ():
        o_que = str(linha.get("o_que") or "")
        carimbo = float(linha.get("carimbo") or 0.0)
        if o_que == "ponte subiu" and not linha.get("alem_do_limite"):
            continue
        if o_que in FRASE_DO_DIARIO:
            pousar(_mac(linha.get("adaptador")), carimbo, FRASE_DO_DIARIO[o_que])
        elif o_que == PAROU_DE_REINICIAR:
            dita = entrada_a_entrada.com_o_nome_dela(
                linha, maquina=maquina, controladores=controladores)
            pousar(caminhos.get(str(linha.get("porta") or ""), ""), carimbo,
                   str(dita.get("frase") or "O adaptador não se cura sozinho. Tire e ponha ele."))
    for lista in por.values():
        lista.sort(key=lambda q: q["carimbo"], reverse=True)
    return por


#: O tipo de um aparelho Bluetooth pela classe dele (o «Class of Device»):
#: áudio e periféricos são os que dividem o rádio com os controles.
def _tipo_pela_classe(classe: int | None) -> str:
    if not isinstance(classe, int):
        return "outro"
    maior, menor = (classe >> 8) & 0x1F, (classe >> 2) & 0x3F
    if maior == 0x04:
        return "fone" if menor in (0x01, 0x06) else "caixa"
    if maior == 0x05:
        # O combo (teclado com touchpad) é teclado: é o desenho que ela reconhece.
        return {0x10: "teclado", 0x20: "mouse", 0x30: "teclado"}.get(menor & 0x30, "outro")
    if maior == 0x06 and menor & 0x08:
        return "webcam"
    return "outro"


def _tipo_do_aparelho(icone: str, classe: int | None) -> str:
    """O tipo pelo ``Icon`` do BlueZ primeiro, e pela classe quando ele cala.

    O ``Icon`` é o que alcança o aparelho LE, que não tem ``Class`` (o passo b7
    da lista dela). Os dois são do BlueZ — a tela não casa tipo por nome.
    """
    return TIPO_PELO_ICONE.get(str(icone or "")) or _tipo_pela_classe(classe)


#: Os nomes de FÁBRICA dos controles: um ``Alias`` igual a um deles é o BlueZ
#: repetindo o ``Name``, e não um nome que ela deu.
_NOMES_DE_FABRICA = ("DualSense", "Wireless Controller")


def _e_nome_de_fabrica(nome: str) -> bool:
    return any(nome.startswith(f) for f in _NOMES_DE_FABRICA)


def _nomes_por_endereco(aparelhos_bz: tuple[Any, ...]) -> dict[str, str]:
    """O nome que ela deu a cada controle, pelo ENDEREÇO — um só por aparelho.

    O BlueZ guarda o ``Alias`` por OBJETO, um por adaptador que conhece o
    aparelho, e o dicionário de antes pegava o ÚLTIMO da árvore: com o controle
    pareado em dois adaptadores, a tela podia ler o objeto velho, com outro
    nome ou nenhum (a lista dela de 25/09, passo a2 — *«O vermelho era P4,
    reconectou como P3, e a tela mostrava o nome errado»*). Vale o do objeto
    CONECTADO; sem nome ali, o de qualquer outro; nome de fábrica não é nome.
    <!-- noqa-acento: citação literal dela -->
    """
    nomes: dict[str, str] = {}
    for a in sorted(aparelhos_bz, key=lambda a: getattr(a, "conectado", None) is not True):
        nome = str(getattr(a, "nome", "") or "").strip()
        endereco = _mac(getattr(a, "endereco", ""))
        if nome and endereco and not _e_nome_de_fabrica(nome) and endereco not in nomes:
            nomes[endereco] = nome
    return nomes


def cena_do_radio(ctx: Contexto) -> dict[str, Any]:
    """A cena da seção pela máquina dela — os donos, e nada estimado (R10)."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import entrada_a_entrada
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    st: dict[str, Any] = ctx.state or {}
    ar: dict[str, Any] = _dicionario(st.get("radio_ar"))
    governador: dict[str, Any] = _dicionario(st.get("radio_governador"))
    central: dict[str, Any] = _dicionario(st.get("radio_central"))
    bluez = _em_fundo("bluez", _ler_o_bluez, 3.0)
    lida = _em_fundo("maquina", _ler_a_maquina, 5.0)
    maquina, controladores = lida if lida else (None, {})
    mesa = _mesa_do_radio()
    adaptadores_bz, aparelhos_bz = bluez if bluez else ((), ())

    por_hci = {str(getattr(a, "interface", "")): a for a in getattr(mesa, "adaptadores", ()) or ()}
    enderecos: list[str] = []
    for a in adaptadores_bz:
        if _mac(a.endereco) and _mac(a.endereco) not in enderecos:
            enderecos.append(_mac(a.endereco))
    for chave in (*ar.keys(), *governador.keys()):
        if _mac(chave) and _mac(chave) not in enderecos:
            enderecos.append(_mac(chave))
    bz_de = {_mac(a.endereco): a for a in adaptadores_bz}

    agora = time.time()
    prazo = _prazo_do_pendente()
    movimentos = [m for m in central.get("movimentos") or () if isinstance(m, dict)]
    esperando = [m for m in movimentos if m.get("estado") == "esperando"
                 and agora - float(m.get("quando") or 0.0) <= prazo]
    ocupado = bool(esperando)

    # Quem está COLADO em outro rádio — a mesa já mediu (`Mesa.apertadas`).
    apertadas = {n for par in getattr(mesa, "apertadas", ()) or () for n in par}

    lugares: list[dict[str, Any]] = []
    caminho_para_endereco: dict[str, str] = {}
    evitados: list[dict[str, Any]] = []
    canais_medidos: dict[str, bool] = {}
    portas: list[dict[str, Any]] = []
    for end in enderecos:
        bz = bz_de.get(end)
        mz = por_hci.get(str(getattr(bz, "hci", ""))) if bz is not None else None
        lugar = str(getattr(bz, "lugar", "") or getattr(mz, "lugar", "") or "")
        caminho = str(getattr(mz, "caminho", "") or "")
        if caminho:
            caminho_para_endereco[caminho] = end
        declarado = maquina.lugares.get(lugar) if (maquina is not None and lugar) else None
        # Antes da primeira leitura do `maquina.json` (ela é de fundo), o
        # documento em branco: a porta aparece como «Entrada 1.2» e não como
        # «Dentro da máquina» — que é só do adaptador sem porta.
        documento = maquina if maquina is not None else MaquinaConfig()
        entrada = entrada_a_entrada.rotulo_da_entrada(
            lugar, maquina=documento, controladores=controladores) if lugar else None
        face = entrada_a_entrada.face_do_lugar(
            lugar, maquina=documento, controladores=controladores) if lugar else None
        publicado = ar.get(end) or next((v for k, v in ar.items() if _mac(k) == end), None) or {}
        lista = publicado.get("canais_evitados") if isinstance(publicado, dict) else None
        if isinstance(lista, list):
            canais_medidos[end] = True
            evitados.extend({"lugar": end, "ini": a, "fim": b} for a, b in _faixas(lista))
        junto = ""
        no = str(getattr(mz, "no", "") or "")
        if no and no in apertadas:
            junto = "colado em outro rádio"
        lugares.append({
            "id": end, "lugar": lugar,
            "nome": str(getattr(declarado, "nome", "") or ""),
            # «Dentro da máquina» é RESPOSTA do BlueZ (o adaptador que ele
            # descreveu sem porta), não o que sobra: um endereço que só o
            # daemon publicou — o primeiro tique, com o BlueZ ainda no fio —
            # não tem porta sabida, e a linha e as perguntas não afirmam nada.
            # As perguntas esperam também o NOME (o `maquina.json`): a janela
            # do pedido congela o texto, e «a Entrada 1.2» no lugar do «Sala»
            # que ela deu ficaria lá até ela responder.
            "entrada": entrada or (DENTRO_DA_MAQUINA if bz is not None else ""),
            "sabido": bz is not None and maquina is not None,
            "face": face or "",
            "hub": bool(getattr(mz, "atras_de_hub", False)),
            "varrendo": bool(getattr(bz, "varrendo", False)),
            "junto": junto, "usb3": False,
            "conectando": any(not m.get("aparelho") and _mac(m.get("destino")) == end
                              for m in esperando),
            "chegou": [str(m.get("aparelho") or "") for m in movimentos
                       if m.get("estado") == "chegou" and _mac(m.get("destino")) == end],
        })
        if caminho:
            portas.append({"id": f"porta-{end}", "caminho": caminho, "usb": "2.0",
                           "ocupa": end, "grupo": _grupo_da_porta(caminho),
                           "rotulo": entrada or caminho})
    sino = _quedas_por_adaptador(_em_fundo("sino", _ler_o_historico, 60.0),
                                 caminho_para_endereco, maquina, controladores)
    lido_do_sino = _FUNDO.get("sino", (0.0, None))[1] or {}
    desde = str(lido_do_sino.get("desde") or "")
    for lug in lugares:
        lug["quedas"] = sino.get(lug["id"], [])
        if lug["quedas"] and desde:
            lug["quedas_desde"] = desde[8:10] + "/" + desde[5:7]

    aparelhos = _aparelhos_da_cena(ctx, st, governador, esperando, aparelhos_bz,
                                   {str(getattr(a, "caminho", "")): _mac(a.endereco)
                                    for a in adaptadores_bz}, enderecos)
    declarados = _radios_declarados(_declaracao())
    para_id, rotulo_do_tipo = _tipos_de_radio()
    vizinhos = []
    for r in getattr(mesa, "radios", ()) or ():
        chave = _chave_do_radio(r)
        tipo = declarados.get(chave, "")
        # A SUGESTÃO DO KERNEL só entra enquanto ela não respondeu, e só na dica
        # — vestida de pergunta; o `maquina.json` só recebe a palavra DELA.
        sugestao = "" if tipo else _sugestao_do_vizinho(str(getattr(r, "no", "") or ""), para_id)
        vizinhos.append({"id": chave, "tipo": tipo, "nome": rotulo_do_tipo.get(tipo, ""),
                         "sugestao": sugestao, "sugestao_tipo": para_id.get(sugestao, "")})
        if getattr(r, "caminho", ""):
            portas.append({"id": f"porta-{chave}", "caminho": str(r.caminho),
                           "usb": "3.0" if getattr(r, "usb3", False) else "2.0",
                           "ocupa": chave, "grupo": _grupo_da_porta(str(r.caminho)),
                           "rotulo": str(r.caminho)})
    pedido = None
    for end, publicado in governador.items():
        for p in (publicado or {}).get("pedidos") or ():
            pedido = {"uniq": str(p.get("uniq") or ""), "tipo": str(p.get("tipo") or ""),
                      "vagas": [_mac(v) for v in p.get("vagas") or ()], "lugar": _mac(end)}
            break
        if pedido:
            break
    if pedido:
        quem = str(pedido["uniq"])
        dono = next((a for a in aparelhos if _so_hex(str(a["id"])) == _so_hex(quem)), None)
        pedido["uniq"] = str(dono["id"]) if dono else quem
    proposta = central.get("proposta") if isinstance(central.get("proposta"), dict) else None
    if proposta:
        dono = next((a for a in aparelhos
                     if _so_hex(a["id"]) == _so_hex(str(proposta.get("controle") or ""))), None)
        proposta = ({"controle": dono["id"], "destino": _mac(proposta.get("destino"))}
                    if dono else None)
    lugares = _na_ordem_dela(lugares)
    cena = {
        # ALGUÉM RESPONDEU sobre os adaptadores: o BlueZ, ou o daemon pelo
        # `radio_ar`/`radio_governador`. Sem isso a sala não diz «nenhum».
        "lido": bluez is not None or bool(ar) or bool(governador),
        "lugares": lugares, "aparelhos": aparelhos, "evitados": evitados,
        "canais_medidos": canais_medidos, "espectro": [], "vizinhos": vizinhos,
        "portas": portas, "pedido": pedido, "proposta": proposta, "ocupado": ocupado,
        "aberto": _o_aberto(lugares, aparelhos, proposta),
        "perto": _perto(aparelhos_bz, adaptadores_bz, aparelhos),
    }
    cena["destino_do_conectar"] = _destino_do_conectar(cena, st)
    return cena


def _o_aberto(lugares: list[dict[str, Any]], aparelhos: list[dict[str, Any]],
              proposta: dict[str, Any] | None = None) -> str | None:
    """O adaptador aberto no acordeão.

    COM UM ADAPTADOR SÓ NA MÁQUINA, A CAIXA DELE NASCE E FICA ABERTA — decisão
    dela, 25/09/2026: *«Essa área se só tiver um conector ela tá sempre
    aberta.»* Não há outra para abrir no lugar, e fechar a única esconderia os
    controles atrás de um clique a mais. Com mais de um, o que ela abriu; sem
    escolha dela, o que mais passou do limite; e sem esse, o da lâmpada.
    <!-- noqa-acento: citação literal dela -->

    A CAIXA DA LÂMPADA ABRE QUANDO NENHUMA OUTRA ABRIRIA (o conferente da
    A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01, 25/09/2026). A lâmpada mora no
    CORPO da caixa do destino — ao lado da vaga de soltar, onde o desenho dela
    a pôs —, e o corpo de uma caixa fechada não aparece. Com os controles
    amontoados sem som (os passos b4 e b5 dela) nenhuma passa do limite de
    pontes, nenhuma caixa abria, e a lâmpada da proposta nova ficava escondida:
    *«A lâmpada não apareceu»* de novo, com a proposta chegando à tela. Abre UMA
    caixa, como no desenho; a escolha dela (abrir outra, ou fechar esta) vence.
    <!-- noqa-acento: citação literal dela -->
    """
    if len(lugares) == 1:
        return str(lugares[0]["id"])
    # A CAIXA QUE ESPERA O GESTO ABRE SOZINHA (25/09/2026, a prova de tela
    # desta sprint): o «Segure PS + Create» mora na linha que espera, DENTRO da
    # caixa do destino, e com ela fechada o que ela precisa fazer custava um
    # clique — a regra de 07/09 desta casa. Enquanto a janela está aberta, a
    # caixa dela vence a escolha; quando o movimento acaba, volta a de antes.
    espera = next((str(a["lugar"]) for a in aparelhos if a.get("esperando") and a.get("lugar")),
                  None) or next((str(lug["id"]) for lug in lugares if lug.get("conectando")), None)
    if espera:
        return espera
    if "lugar" in _ABERTO:
        escolhido = _ABERTO["lugar"]
        return str(escolhido) if escolhido else None
    lampada = str((proposta or {}).get("destino") or "")
    return _o_mais_cheio(lugares, aparelhos) or next(
        (str(lug["id"]) for lug in lugares if str(lug["id"]) == lampada), None)


def _chave_da_ordem(lug: dict[str, Any]) -> str:
    """A chave do adaptador na ordem gravada: o LUGAR (a porta, D3), que é o que
    o nome dela segue; o adaptador sem porta (o da placa-mãe), pelo endereço."""
    return str(lug.get("lugar") or lug.get("id") or "")


def _na_ordem_dela(lugares: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Os adaptadores na ORDEM QUE ELA ARRASTOU — decisão dela, 25/09/2026:
    *«segurar a área do conector e arrastar ela pra mudar de ordem entre
    eles»*, e a ordem fica gravada (``gui_prefs``, o dono do que ela arrasta
    na janela). Quem ela nunca arrastou vem depois, na ordem de sempre.
    <!-- noqa-acento: citação literal dela -->
    """
    ordem = _ordem_gravada()
    if not ordem:
        return lugares
    posicao = {chave: i for i, chave in enumerate(ordem)}
    return sorted(lugares, key=lambda lug: posicao.get(_chave_da_ordem(lug), len(posicao)))


def _ordem_gravada() -> list[str]:
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.gui_prefs import ordem_dos_adaptadores

        return list(ordem_dos_adaptadores())
    except Exception:
        return []


def _o_mais_cheio(lugares: list[dict[str, Any]], aparelhos: list[dict[str, Any]]) -> str | None:
    """O adaptador que mais passou do limite de pontes, ou nenhum."""
    def pontes(lid: str) -> int:
        return sum(1 for a in aparelhos if a.get("lugar") == lid
                   and a.get("tipo") == "controle" and a.get("ponte"))
    cheios = [lug for lug in lugares if pontes(str(lug["id"])) > PONTES_POR_ADAPTADOR]
    if not cheios:
        return None
    return str(max(cheios, key=lambda lug: pontes(str(lug["id"])))["id"])


def _faixas(canais: list[Any]) -> list[tuple[int, int]]:
    """`[20, 21, 22, 30]` → `[(20, 23), (30, 31)]` — o mapa AFH em faixas."""
    faixas: list[tuple[int, int]] = []
    for c in sorted({int(c) for c in canais if isinstance(c, int) and 0 <= c < CANAIS_DO_BT}):
        if faixas and faixas[-1][1] == c:
            faixas[-1] = (faixas[-1][0], c + 1)
        else:
            faixas.append((c, c + 1))
    return faixas


def _grupo_da_porta(caminho: str) -> str:
    """As portas que dividem o mesmo hub — é a proximidade física que conta."""
    pai = caminho.rsplit(".", 1)[0] if "." in caminho else ""
    return pai or "Direto no computador"


def _prazo_do_pendente() -> float:
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations.central_do_radio import PRAZO_DO_PENDENTE_S

        return float(PRAZO_DO_PENDENTE_S)
    except Exception:
        return 120.0


def _aparelhos_da_cena(ctx: Contexto, st: dict[str, Any], governador: dict[str, Any],
                       esperando: list[dict[str, Any]], aparelhos_bz: tuple[Any, ...],
                       endereco_do_caminho: dict[str, str],
                       enderecos: list[str]) -> list[dict[str, Any]]:
    """Os controles pelo `state_full` (as quatro chaves por controle) e o resto pelo BlueZ."""
    da_mesa = {str(m.get("uniq") or ""): m for m in ctx.mesa}
    alem = {_so_hex(str(p.get("uniq") or "")): (p.get("tipo"), bool(p.get("alem_do_limite")))
            for publicado in governador.values()
            for p in _dicionario(publicado).get("pontes") or ()}
    # A ORDEM EM QUE AS PONTES CHEGARAM, que é a do governador (ver `_pontes`).
    ordem_da_vaga = {_so_hex(str(p.get("uniq") or "")): i
                     for publicado in governador.values()
                     for i, p in enumerate(_dicionario(publicado).get("pontes") or ())}
    alias = _nomes_por_endereco(aparelhos_bz)
    fora: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for c in st.get("controllers") or ():
        if not isinstance(c, dict) or str(c.get("transport") or "").lower() != "bt":
            continue
        uniq = str(c.get("uniq") or "")
        adaptador = _mac(c.get("adaptador"))
        if not uniq or adaptador not in enderecos:
            continue
        eu = da_mesa.get(uniq) or {}
        slug = str(eu.get("cor") or "")
        cor = _hex_do_plastico(slug)
        audio = _dicionario(c.get("audio"))
        ponte = c.get("ponte_do_radio")
        tipo_gov, passou = alem.get(_so_hex(uniq), (None, False))
        if ponte not in ("som", "haptica") and tipo_gov in ("som", "vibracao"):
            ponte = "som" if tipo_gov == "som" else "haptica"
        nome_bz = alias.get(_mac(uniq), "")
        vaga: dict[str, Any] = {}
        if _so_hex(uniq) in ordem_da_vaga:
            vaga["ordem_da_vaga"] = ordem_da_vaga[_so_hex(uniq)]
        fora.append({
            **vaga,
            "id": uniq, "tipo": "controle", "lugar": adaptador,
            "nome": nome_bz,
            # O NÚMERO É DO DAEMON VIVO (a mesa do tique), e o nome é do endereço.
            "jogador": eu.get("jogador"),
            "rotulo": f"Player {eu['jogador']}" if eu.get("jogador") else "DualSense",
            "cor": cor if cor.startswith("#") else "",
            "cor_nome": "" if str(eu.get("nome") or "") in ("", _cor_desconhecida())
            else str(eu["nome"]),
            "mic": (not audio.get("mic_mudo")) if "mic_mudo" in audio
            else bool(c.get("hz_voz")),
            "ponte": ponte if ponte in ("som", "haptica") else None, "alem": passou,
            "hz_mov": c.get("hz_movimento"), "hz_voz": c.get("hz_voz"), "luz": True,
            "esperando": False, "fixo": False,
        })
        vistos.add(_so_hex(uniq))
    # QUEM ESTÁ SENDO MOVIDO JÁ SAIU DAQUI e espera no destino: é a linha que
    # diz «Segure PS + Create» (R1), com a vaga de ponte guardada.
    for m in esperando:
        quem = _so_hex(str(m.get("aparelho") or ""))
        if not quem:
            continue
        ja = next((a for a in fora if _so_hex(a["id"]) == quem), None)
        if ja is not None:
            ja.update(lugar=_mac(m.get("destino")), esperando=True)
            continue
        eu = next((m2 for u, m2 in da_mesa.items() if _so_hex(u) == quem), {})
        slug = str(eu.get("cor") or "")
        cor = _hex_do_plastico(slug)
        # O QUE ESTÁ ESPERANDO, PELO QUE A CENTRAL LEU ANTES DE ESQUECER A
        # ORIGEM: depois dela o BlueZ não tem mais objeto do aparelho, e o
        # daemon já não o publica (desligado). Sem a classe, um teclado virava
        # «outro» — e o controle, um DualSense sem nome. O `Icon` vem junto: é o
        # único tipo do aparelho de baixo consumo, que não tem classe (o mesmo
        # dono da linha de quem está ligado, `_tipo_do_aparelho`).
        classe = m.get("classe")
        tipo = ("controle" if m.get("e_controle")
                else _tipo_do_aparelho(str(m.get("icone") or ""),
                                       classe if isinstance(classe, int) else None))
        fora.append({"id": str(m.get("aparelho")), "tipo": tipo,
                     "lugar": _mac(m.get("destino")), "nome": str(m.get("nome") or ""),
                     "modalias": str(m.get("modalias") or ""),
                     "jogador": eu.get("jogador"),
                     "rotulo": f"Player {eu['jogador']}" if eu.get("jogador") else "",
                     "cor": cor if cor.startswith("#") else "",
                     "cor_nome": "" if str(eu.get("nome") or "") in ("", _cor_desconhecida())
                     else str(eu["nome"]),
                     "esperando": True, "fixo": False})
        vistos.add(quem)
    for a in aparelhos_bz:
        endereco = _mac(a.endereco)
        adaptador = endereco_do_caminho.get(str(a.adaptador), "")
        # Um DualSense que o daemon não publica não vira «outro aparelho».
        if (not a.conectado or not adaptador or _so_hex(endereco) in vistos
                or "V054C" in str(getattr(a, "modalias", "")).upper()):
            continue
        fora.append({"id": endereco,
                     "tipo": _tipo_do_aparelho(getattr(a, "icone", ""), a.classe),
                     "lugar": adaptador,
                     "nome": str(a.nome or ""), "rotulo": str(a.nome or ""),
                     "esperando": False, "fixo": False})
        vistos.add(_so_hex(endereco))
    return fora


def _perto(aparelhos_bz: tuple[Any, ...], adaptadores_bz: tuple[Any, ...],
           ja: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """O que o rádio está vendo e não está ligado — a lista do «Conectar»."""
    ligados = {_so_hex(a["id"]) for a in ja}
    vistos: dict[str, dict[str, Any]] = {}
    for a in aparelhos_bz:
        if a.conectado or a.rssi is None or _so_hex(a.endereco) in ligados:
            continue
        vistos[_mac(a.endereco)] = {
            "id": _mac(a.endereco), "nome": a.nome or _mac(a.endereco),
            "tipo": ("controle" if "054C" in str(a.modalias).upper()
                     else _tipo_do_aparelho(getattr(a, "icone", ""), a.classe)),
            "forca": a.rssi, "conhecido": bool(a.pareado),
        }
    return sorted(vistos.values(), key=lambda a: -(a["forca"] or -999))


def _destino_do_conectar(cena: dict[str, Any], st: dict[str, Any]) -> str:
    """O destino que a tela mostra no «Conectar»: o que ela escolheu no chip,
    ou a D8 (`plano_de_radio.ordem_dos_destinos`). É ESTE que vai no
    `radio.mover` — a ordem da tela e a da central não divergem no empate."""
    if not cena["lugares"]:
        return ""
    # A JANELA ABERTA É A VERDADE DO CHIP (25/09/2026, a prova de tela): o
    # adaptador em que a janela abriu passa a VARRER, e a D8 manda quem varre
    # para o fim — o chip do «Procurando» pulava para outro adaptador com a
    # janela aberta no primeiro. Enquanto um movimento espera, o chip é o dele.
    for m in (_dicionario(st.get("radio_central")).get("movimentos") or ()):
        if isinstance(m, dict) and m.get("estado") == "esperando" and m.get("destino"):
            aberto = _mac(str(m.get("destino")))
            if any(lug["id"] == aberto for lug in cena["lugares"]):
                return aberto
    escolhido = _ABERTO.get("destino")
    if escolhido and any(lug["id"] == escolhido for lug in cena["lugares"]):
        return str(escolhido)
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations import plano_de_radio

        controles = [c for c in st.get("controllers") or ()
                     if isinstance(c, dict) and c.get("adaptador")]
        planos = plano_de_radio.plano_por_adaptador(
            controles, adaptadores=[str(lug["id"]).lower() for lug in cena["lugares"]])
        ordem = plano_de_radio.ordem_dos_destinos(
            planos, varrendo=[lug["id"] for lug in cena["lugares"] if lug.get("varrendo")])
        if ordem:
            return _mac(ordem[0].endereco)
    return str(cena["lugares"][0]["id"])


#: O que a tela está mostrando AGORA — o gesto age sobre a cena que ela viu,
#: como o ⊘ do Check-up age sobre `_ORDENS_NA_TELA`.
_CENA_NA_TELA: dict[str, Any] = {}
#: O adaptador aberto no acordeão e o destino escolhido no «Conectar».
_ABERTO: dict[str, Any] = {}


def _laco() -> Any:
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import entrada_a_entrada

    return entrada_a_entrada.o_laco()


def _campos_da_cerimonia() -> dict[str, Any]:
    """As três telas do «Mapear Entrada a Entrada», pelo laço (ENTRADA-A-ENTRADA-02).

    O laço anda no tique só enquanto a cerimônia está aberta; fechada, ele não
    lê nada. A página segue `entrada-tela` para a âncora da fase.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.widgets import calibrar_entradas as calib
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee

    laco = _laco()
    foto = laco.estado()
    if foto.get("estado") not in (None, ee.PARADO, ee.FIM):
        foto = laco.olhar()
    contador, quem = "", ""
    if foto.get("estado") == ee.SENTADA:
        contador = (f'entrada {foto.get("passo")} de {foto.get("total")} '
                    f'<span class="pt">·</span> {calib.SEM_SAIR_DA_CADEIRA}')
        pergunta = foto.get("pergunta") or {}
        quem = (f'{_x(pergunta.get("especie") or "")} <span class="pt">·</span> '
                f'<code>{_x(pergunta.get("caminho") or "")}</code>') if pergunta else ""
    elif foto.get("estado") == ee.EM_PE:
        contador = f'entrada {foto.get("passo")} de {foto.get("total")}'
        quem = calib.PROCURANDO
    elif foto.get("estado") == ee.FIM:
        quem = _x(calib.CONVITE_EM_PE)
    # O VAZIO É O `NADA_A_DIZER`: um `""` viraria travessão nas três telas.
    nada = _monta().NADA_A_DIZER
    return {"entrada-tela": foto.get("tela") or "", "entrada-contador": contador or nada,
            "entrada-quem": quem or nada}


def campos_do_radio(ctx: Contexto) -> dict[str, Any]:
    """Os campos da seção Rádio e Adaptadores, pela cena da máquina dela."""
    global _CENA_NA_TELA
    cena = cena_do_radio(ctx)
    _CENA_NA_TELA = cena
    campos = campos_da_secao(cena)
    with contextlib.suppress(Exception):
        campos.update(_campos_da_cerimonia())
    return campos


def _lugar_na_tela(o: dict[str, Any]) -> dict[str, Any]:
    alvo = str(o.get("alvo") or "")
    lug = next((lg for lg in _CENA_NA_TELA.get("lugares", ()) if lg["id"] == alvo), None)
    if not isinstance(lug, dict):
        raise ValueError(f"o clique não disse um adaptador que está na tela ({alvo!r})")
    return lug


def _aparelho_na_tela(alvo: str) -> dict[str, Any]:
    ap = next((a for a in _CENA_NA_TELA.get("aparelhos", ()) if a["id"] == alvo), None)
    if not isinstance(ap, dict):
        raise ValueError(f"o clique não disse um aparelho que está na tela ({alvo!r})")
    return ap


# -- os gestos da seção -------------------------------------------------------


@gesto("08-conexoes.html", "abrir-adaptador")
def abrir_adaptador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Abre um adaptador e fecha os outros (acordeão exclusivo, ordem dela).

    Com um adaptador só, ele não fecha: a caixa da máquina de um adaptador
    nasce e FICA aberta (decisão dela, 25/09/2026 — ver :func:`_o_aberto`).
    """
    lug = _lugar_na_tela(o)
    if len(_CENA_NA_TELA.get("lugares") or ()) == 1:
        return {"armou": True}
    _ABERTO["lugar"] = None if _CENA_NA_TELA.get("aberto") == lug["id"] else lug["id"]
    return {"armou": True}


@gesto("08-conexoes.html", "adaptador-reordenar", grava="guardar_ordem_dos_adaptadores")
def adaptador_reordenar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A ordem das caixas que ela arrastou — gravada, e a sala nasce nela.

    Decisão dela, 25/09/2026: *«segurar a área do conector e arrastar ela pra
    mudar de ordem entre eles»*. O roteiro da página solta a caixa no lugar e
    manda a ordem NOVA, de cima para baixo, pelos ``data-id`` das caixas (o
    endereço de cada adaptador); aqui ela vira a chave de cada um — o lugar,
    que é o que o nome dela segue — e vai para o ``gui_prefs``, o dono do que
    ela arrasta na janela. Um id que não está na tela recusa: a ordem nunca
    inventa um adaptador. <!-- noqa-acento: citação literal dela -->
    """
    ids = str(o.get("valor") or "").split()
    na_tela = {str(lug["id"]): lug for lug in _CENA_NA_TELA.get("lugares") or ()}
    if not ids or any(i not in na_tela for i in ids):
        raise ValueError(f"a ordem não disse os adaptadores da tela ({ids!r})")
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.gui_prefs import guardar_ordem_dos_adaptadores

    guardar_ordem_dos_adaptadores([_chave_da_ordem(na_tela[i]) for i in ids])
    _CENA_NA_TELA["lugares"] = [na_tela[i] for i in ids] + [
        lug for i, lug in na_tela.items() if i not in ids]


def _gravar_o_nome(lugar: str, nome: str) -> Any:
    """O nome é do LUGAR (D3) e mora no `maquina.json`; o `Alias` do BlueZ é a
    projeção dele, e quem o escreve é o `bt_active_mode.sh`, UM escritor só
    (TRANSPLANTE-DA-SECAO-01, item 1: eram três)."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.entrada_a_entrada import dar_nome

    feito = dar_nome(lugar, nome)
    _esquecer("maquina")
    _reler_a_declaracao()
    return feito


def _so_o_foco(o: dict[str, Any]) -> bool:
    """O clique que só POSICIONA o cursor num campo de nome: o ouvinte do piloto
    ouve `click` e `change` no mesmo elemento, e o nome só vale no `change`."""
    return str(o.get("evento") or "") == "click"


@gesto("08-conexoes.html", GESTO_DO_APELIDO, grava="dar_nome")
def adaptador_renomear(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O nome que ela dá ao adaptador — no lugar dele, e o adaptador herda."""
    if _so_o_foco(o):
        return {"armou": True}
    lug = _lugar_na_tela(o)
    if not lug.get("lugar"):
        raise RuntimeError("este adaptador é da placa-mãe: não tem entrada a nomear")
    novo = str(o.get("valor") or "").strip()
    if novo == str(lug.get("nome") or ""):
        return None
    feito = _gravar_o_nome(str(lug["lugar"]), novo)
    if not getattr(feito, "gravou", False):
        raise RuntimeError("o nome não foi gravado")
    return None


def _alias_do_aparelho(endereco: str, nome: str) -> Any:
    """O `Alias` de um APARELHO no BlueZ, pelo dono (`bluez_dbus`) — em TODOS
    os objetos dele.

    O NOME É DO APARELHO, E O BLUEZ O GUARDA POR ADAPTADOR. Esta função
    escrevia no PRIMEIRO objeto da árvore; com o controle pareado em dois
    adaptadores, o nome ia para o de onde ele não estava, e a tela lia o outro
    (a lista dela de 25/09, passo a2: *«O nome renomeado não aparece»*). Agora
    vai para todos, e vale onde ele reconectar. Nome vazio devolve o de fábrica
    — o BlueZ faz isso com o ``Alias`` em branco, e a tela volta ao «Player N».
    Devolve a primeira escrita que deu, ou a primeira recusa quando nenhuma deu.
    <!-- noqa-acento: citação literal dela -->
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import bluez_dbus

    dono = bluez_dbus.dono()
    caminhos = dono.caminhos_do_aparelho(endereco)
    if not caminhos:
        raise RuntimeError("o Bluetooth do sistema não achou este aparelho agora")
    escritas = [dono.escrever_propriedade(
        caminho, bluez_dbus.APARELHO, "Alias", "s", nome, quem="tela") for caminho in caminhos]
    _esquecer("bluez")
    return next((e for e in escritas if getattr(e, "feita", False)), escritas[0])


@gesto("08-conexoes.html", "aparelho-renomear", grava="escrever_propriedade")
def aparelho_renomear(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O nome de um aparelho — Vitória, Caixa de som — no `Alias` do BlueZ."""
    if _so_o_foco(o):
        return {"armou": True}
    ap = _aparelho_na_tela(str(o.get("alvo") or ""))
    novo = str(o.get("valor") or "").strip()
    if novo == str(ap.get("nome") or ""):
        return None
    endereco = norm_mac(str(ap["id"])) or ""
    endereco = ":".join(endereco[i:i + 2] for i in range(0, 12, 2)).upper() \
        if len(endereco) == 12 and ":" not in endereco else endereco.upper()
    escrita = _alias_do_aparelho(endereco, novo)
    if not getattr(escrita, "feita", False):
        raise RuntimeError("o Bluetooth do sistema não gravou o nome novo")
    return None


def _mover(p: Any, aparelho: str | None, destino: str) -> dict[str, Any]:
    """`radio.mover` pelo dono (a central) — SEMPRE com o destino que a tela mostrou."""
    if _CENA_NA_TELA.get("ocupado"):
        raise RuntimeError("outro movimento está esperando PS + Create")
    parametros: dict[str, Any] = {"destino": destino}
    if aparelho:
        parametros["aparelho"] = aparelho
    resposta = p.resultado("radio.mover", **parametros)
    status = str((resposta or {}).get("status") or "") if isinstance(resposta, dict) else ""
    if status != "ok":
        # «ocupado» é também «outro movimento em curso»: o botão treme (R8).
        raise RuntimeError(f"o rádio não aceitou agora ({status or 'sem resposta'})")
    return {"armou": True}


@gesto("08-conexoes.html", "confirmar-mudanca", grava="radio.mover")
def confirmar_mudanca(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Mover» (e «Mover e ligar»): o aparelho vai para o destino da pergunta."""
    alvo, destino = str(o.get("alvo") or ""), str(o.get("destino") or "")
    if not alvo or not destino:
        raise ValueError("a pergunta não disse quem vai nem para onde")
    return _mover(p, alvo, destino)


def _ligar_aqui(p: Any, uniq: str) -> None:
    resposta = p.resultado("radio.ponte.ligar_aqui", uniq=uniq)
    if not isinstance(resposta, dict) or resposta.get("status") != "ok":
        raise RuntimeError("a ponte não subiu aqui")


@gesto("08-conexoes.html", "ligar-mesmo-assim", grava="radio.ponte.ligar_aqui")
def ligar_mesmo_assim(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Ligar aqui»: a terceira ponte sobe no adaptador cheio, marcada além do limite (R4)."""
    alvo = str(o.get("alvo") or "")
    if not alvo:
        raise ValueError("a pergunta não disse qual controle")
    _ligar_aqui(p, alvo)


@gesto("08-conexoes.html", "conectar-aparelho", grava="radio.mover")
def conectar_aparelho(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Conectar»: sem alvo, a janela abre no destino da D8 e o controle que
    ela segurar chega; com alvo (um achado que o destino já conhece), é Mover."""
    destino = str(_CENA_NA_TELA.get("destino_do_conectar") or "")
    if not destino:
        raise RuntimeError("não há adaptador Bluetooth para conectar")
    return _mover(p, str(o.get("alvo") or "") or None, destino)


@gesto("08-conexoes.html", "parear-aparelho", grava="radio.mover")
def parear_aparelho(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Parear» um aparelho que o rádio achou, no destino escolhido."""
    alvo = str(o.get("alvo") or "")
    if not alvo:
        raise ValueError("o clique não disse qual aparelho")
    return _mover(p, alvo, str(_CENA_NA_TELA.get("destino_do_conectar") or ""))


@gesto("08-conexoes.html", "escolher-adaptador")
def escolher_adaptador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O chip do «Conectar»: o destino que ela escolheu vale no próximo pedido.

    COM A JANELA ABERTA NOUTRO ADAPTADOR, O CHIP RECUSA (25/09/2026): a janela
    não muda de adaptador no meio, e um chip que acende sem mudar onde a busca
    acontece diria uma coisa e o rádio faria outra. A recusa pisca, sem recado.
    """
    lug = _lugar_na_tela(o)
    if _CENA_NA_TELA.get("ocupado") and lug["id"] != _CENA_NA_TELA.get("destino_do_conectar"):
        raise RuntimeError("a busca já está aberta noutro adaptador")
    _ABERTO["destino"] = lug["id"]
    _CENA_NA_TELA["destino_do_conectar"] = lug["id"]
    return {"armou": True}


@gesto("08-conexoes.html", "equilibrar-radio")
def equilibrar_radio(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Equilibrar»: a proposta da central abre a pergunta; sem proposta, treme (R8)."""
    if _CENA_NA_TELA.get("ocupado"):
        raise RuntimeError("esperando um controle chegar")
    if not _CENA_NA_TELA.get("proposta"):
        raise RuntimeError("já está equilibrado")
    return {"armou": True}


def _so_abre() -> dict[str, Any]:
    """Os gestos que só ABREM o que já veio pintado: a página abre, o Python
    confere que há o que abrir e responde sem piscar."""
    return {"armou": True}


@gesto("08-conexoes.html", "cancelar-mudanca")
def cancelar_mudanca(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Cancelar» a pergunta: nada muda no rádio."""
    return _so_abre()


@gesto("08-conexoes.html", "trazer-para-ca")
def trazer_para_ca(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Arraste para cá» clicado: a lista de quem pode vir (a página a abre)."""
    _lugar_na_tela(o)
    if _CENA_NA_TELA.get("ocupado"):
        raise RuntimeError("esperando um controle chegar")
    return _so_abre()


@gesto("08-conexoes.html", "sugerir-alocacao")
def sugerir_alocacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """A lâmpada: a proposta da central para este adaptador (a página a mostra)."""
    lug = _lugar_na_tela(o)
    proposta = _CENA_NA_TELA.get("proposta") or {}
    if proposta.get("destino") != lug["id"]:
        raise RuntimeError("não há quem funcione melhor aqui agora")
    return _so_abre()


@gesto("08-conexoes.html", "aceitar-sugestao")
def aceitar_sugestao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Mover» do balão: abre a MESMA pergunta de todo mover (R7)."""
    return _so_abre()


@gesto("08-conexoes.html", "adaptador-historico")
def adaptador_historico(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O sino: o que aconteceu com este adaptador, pela hora (a página o abre)."""
    lug = _lugar_na_tela(o)
    if not lug.get("quedas"):
        raise RuntimeError("nada aconteceu com este adaptador")
    return _so_abre()


@gesto("08-conexoes.html", "custo-mic", grava="mic_canal_set_detalhado")
def custo_mic(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O microfone de um controle: o MESMO ato do 🎙 da aba Controles (D-12).

    O MESMO ATO, E NÃO UMA CÓPIA DELE: o gesto é o `mudo` da aba 02, chamado.
    A primeira versão deste gesto (TRANSPLANTE-DA-SECAO-01) refazia o pedido ao
    daemon e parava ali — e com isso o perfil não lembrava o microfone ligado
    por aqui, as recusas do alvo não chegavam, e a mesma chave da mesa tinha
    dois comportamentos conforme a aba. Um dono só: o que a 02 grava, confessa
    e recusa vale igual nesta linha.
    """
    uniq = str(o.get("alvo") or "")
    if not uniq or not ctx.por_uniq(uniq):
        raise ValueError("o clique não disse em qual controle")
    _o_mudo_da_aba_02(ctx, {"uniq": uniq, "mudo": "microfone"}, p)


# -- as três telas do «Mapear Entrada a Entrada» ------------------------------


@gesto("08-conexoes.html", "entrada-comecar")
def entrada_comecar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Abrir a âncora começa o laço — no lugar do «Onde fica?», se veio de um."""
    _laco().comecar(str(o.get("alvo") or "") or None)
    return {"armou": True}


@gesto("08-conexoes.html", "entrada-face", grava="responder")
def entrada_face(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A resposta dela — uma das quatro faces do produto —, gravada na hora."""
    face = str(o.get("face") or o.get("valor") or "")
    gravacao = _laco().responder(face)
    _esquecer("maquina")
    if not gravacao.gravou:
        raise RuntimeError("a entrada não foi gravada")


@gesto("08-conexoes.html", "entrada-pular")
def entrada_pular(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Não sei onde fica»: não grava, e não pergunta de novo nesta vez."""
    _laco().pular()
    return {"armou": True}


@gesto("08-conexoes.html", "entrada-levantar")
def entrada_levantar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Vou mostrar agora»: a fase em pé."""
    _laco().levantar()
    return {"armou": True}


@gesto("08-conexoes.html", "entrada-nao-alcanco", grava="nao_alcanco")
def entrada_nao_alcanco(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Não alcanço»: a vaga sai da conta de vez."""
    _laco().nao_alcanco()
    _esquecer("maquina")


@gesto("08-conexoes.html", "entrada-parar")
def entrada_parar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Já chega por hoje»: fecha, e nada se perde — cada resposta já foi."""
    _laco().parar()
    return {"armou": True}


PONTE = {"chamar", "machine_declare", "resultado", "mic_canal_set_detalhado"}
METODOS = {"controller.target.set", "radio.mover", "radio.ponte.ligar_aqui"}


#: O QUE ESTA ABA DECLARA À RÉGUA — o piso e as provas moram AQUI, e não no
#: teste, para que ligar uma aba não exija editar um arquivo que oito pessoas
#: editariam ao mesmo tempo.
PAGINA = "08-conexoes.html"
#: 16 → 37 em 23/09/2026: a seção do rádio trouxe os gestos do desenho aprovado
#: e a cerimônia do «Mapear Entrada a Entrada» (TRANSPLANTE-DA-SECAO-01).
PISO_DA_ABA = 37
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
    # DESLIGAR GRAVA `False` desde 18/09/2026: com o default invertido (a
    # ausência LIGA), `None` seria o botão que não desliga. Ver `mic_existe`.
    {"pagina": PAGINA, "gesto": "mic-existe", "clique": {"valor": "Desligado"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": False}}}], {})]},
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
#:
#: `adaptador-reordenar` (25/09/2026) grava a ordem das caixas no
#: `gui_preferences.json`, o arquivo da JANELA: o daemon nem sabe dela.
#:
#: OS QUATRO DA SEÇÃO DO RÁDIO — 23/09/2026: `adaptador-renomear`,
#: `entrada-face` e `entrada-nao-alcanco` gravam no `maquina.json` (o nome e o
#: mapa das entradas), e `aparelho-renomear` grava o `Alias` no BlueZ. O
#: `state_full` não publica nenhum dos três.
#:
#: OS SEIS DO CHECK-UP — A-08-O-CHECKUP-ABSORVE-A-GESTAO-01, 25/09/2026:
#: `dono-renomear` grava o `Alias` no BlueZ; `economia-do-controle` grava
#: `controles[uniq].economia` no `maquina.json`; `mapear-gravar` grava a porta
#: da vez no `maquina.json` pelo dono do mapa; `mapear-comecar` e `mapear-parar`
#: só ligam e desligam o olhar do dono no processo da interface; e
#: `checkup-atualizar` só relê. O `state_full` não publica nenhum deles.
SEM_ECO = ("sala-altura", "sala-visada", "mic-existe", "vizinho-o-que-e",
           "ignorar", "examinar-portas", "teto-da-vibracao",
           "escolher-aparelho", "escolher-entrada", "tirar-daqui",
           "nova-entrada", "nova-extensao", "nova-face",
           "adaptador-renomear", "aparelho-renomear", "entrada-face",
           "entrada-nao-alcanco", "adaptador-reordenar",
           "dono-renomear", "economia-do-controle", "mapear-gravar", "checkup-atualizar", "mapear-comecar", "mapear-parar")


# ---------------------------------------------------------------------------
# A LINHA DE CADA CONTROLE NO CHECK-UP — A-08-O-CHECKUP-ABSORVE-A-GESTAO-01,
# 25/09/2026. Pedido dela: *«aproveitariamos para unificarmos o Gestão de
# Controles ao Check-up»*, e a linha passa a dizer o ESTADO do controle agora,
# só leitura, com o ✓ de «tudo certo». <!-- noqa-acento: citação literal dela -->
#
# UM DONO PARA A PEÇA E DOIS CHAMADORES: o gerador (`aba08.linha_do_controle`)
# desenha a cena da bancada com as mesmas funções, e este pacote as chama a
# cada tique com o daemon vivo. Nada do que a linha diz é digitado no desenho.
# ---------------------------------------------------------------------------
#: O sinal de «tudo certo». Ele é o mesmo nos seis selos, e o `ok` da classe é
#: o que a folha pinta de verde; `warn` é o laranja do que pede olho.
CERTO = "✓"
#: «Modo de conexão»: o caminho que o jogo usa para falar com este controle.
#: `native_mode` é do daemon (o jogo lê o DualSense de verdade); fora dele, o
#: jogo fala com o controle que o Hefesto apresenta.
MODO_NATIVO = "Nativo"
MODO_PELO_HEFESTO = "Pelo Hefesto"


def selo_do_estado(rotulo: str, valor: str = "", estado: str = "ok") -> str:
    """Um selo da linha: «Mic ✓», «Bateria 64% · carregando», «Visto como Xbox 360».

    `estado` é `ok` (o ✓ verde), `warn` (laranja, sem ✓) ou `""` (neutro: é
    informação, não juízo — o modo e o «visto como» não estão certos nem
    errados). O VALOR vai em negrito; o rótulo é a palavra fixa do selo.
    """
    miolo = html.escape(rotulo)
    if valor:
        miolo += f" <b>{html.escape(valor)}</b>"
    if estado == "ok":
        miolo += f' <i class="certo">{CERTO}</i>'
    return f'<span class="est {estado}">{miolo}</span>' if estado else f'<span class="est">{miolo}</span>'


def _estado_de_carga(c: dict[str, Any]) -> str:
    """A palavra do estado de carga, pelo dono da aba 02 (`carga_na_tela`)."""
    try:
        from .a02_controles import carga_na_tela

        return str(carga_na_tela(c.get("battery_state")) or "")
    except Exception:
        return ""


def estado_do_controle(c: dict[str, Any], eu: dict[str, Any], st: dict[str, Any],
                       declaracao: Any) -> dict[str, str]:
    """Os seis selos de UM controle, lidos do daemon vivo e da declaração.

    `c` é a entrada do `state_full` (o `ctx.conectados`), `eu` a da mesa (o
    número e a máscara por aparelho), `st` o estado inteiro. Vale para todo
    transporte e todo modo: nenhum ramo pergunta qual é o controle nem quantos
    há na mesa.
    """
    uniq = str(c.get("uniq") or "")
    via = str(c.get("transport") or "").lower()
    audio = c.get("audio") if isinstance(c.get("audio"), dict) else {}

    # O MIC: ✓ também desligado, quando foi escolha dela (a declaração diz).
    if not _mic_declarado(declaracao, uniq):
        mic = selo_do_estado("Mic", "desligado")
    elif audio.get("mic_mudo") is True:
        mic = selo_do_estado("Mic", "mudo")
    elif via == "bt" and uniq not in (st.get("pontes_confirmadas") or {}) \
            and not c.get("hz_voz"):
        # pelo rádio o microfone só chega por uma ponte; sem ela confirmada e
        # sem voz medida, ele não está chegando — e isso não é «certo».
        mic = selo_do_estado("Mic", "sem ponte", "warn")
    else:
        mic = selo_do_estado("Mic")

    # O SOM: o bloco `speaker` só existe quando o daemon leu o alto-falante.
    fala = c.get("speaker") if isinstance(c.get("speaker"), dict) else None
    if fala is None:
        som = selo_do_estado("Som", TRAVESSAO_DA_LINHA, "")
    elif fala.get("muted"):
        som = selo_do_estado("Som", "mudo")
    else:
        som = selo_do_estado("Som")

    modo = selo_do_estado("Modo de conexão",
                          MODO_NATIVO if st.get("native_mode") else MODO_PELO_HEFESTO, "")
    visto = selo_do_estado("Visto como", str(eu.get("mascara") or TRAVESSAO_DA_LINHA), "")

    # A CONEXÃO: no cabo não há o que engasgar; no rádio quem diz é o
    # movimento medido (o mesmo `_e_pouco` que pinta a linha de Rádio e
    # Adaptadores). Sem medida, não há juízo.
    hz = c.get("hz_movimento")
    if via == "usb":
        conexao = selo_do_estado("Conexão estável")
    elif _e_pouco(hz):
        conexao = selo_do_estado("Conexão", "instável", "warn")
    elif isinstance(hz, (int, float)) and not isinstance(hz, bool):
        conexao = selo_do_estado("Conexão estável")
    else:
        conexao = selo_do_estado("Conexão", TRAVESSAO_DA_LINHA, "")

    carga = _estado_de_carga(c)
    bateria_txt = _texto_da_bateria(c.get("battery_pct"))
    if carga:
        bateria_txt = f"{bateria_txt} · {carga.lower()}"
    bateria = selo_do_estado("Bateria", bateria_txt, "")

    return {"est-mic": mic, "est-som": som, "est-modo": modo, "est-visto": visto,
            "est-conexao": conexao, "est-bateria": bateria}


#: O travessão da linha: *«isto eu não sei»*, o mesmo do `pacotes.__init__`.
TRAVESSAO_DA_LINHA = "—"


def economia_do_controle(declaracao: Any, uniq: str) -> tuple[bool | None, bool]:
    """``(a escolha deste controle, a mesa está em «Bateria longa»?)``.

    O contrato é o da O-MODO-ECONOMIA-POR-CONTROLE-01: a escolha é
    ``controles[uniq].economia`` e a mesa é ``schema.mesa_em_economia`` sobre o
    teto do orçamento — a mesma declaração que o ``_orcamento_da_mesa`` lê.
    """
    from hefesto_dualsense4unix.profiles import schema

    try:
        declarado = (declaracao.controles or {}).get(_so_hex(uniq))
        escolha = getattr(declarado, "economia", None)
    except Exception:
        escolha = None
    teto = getattr(getattr(declaracao, "orcamento", None), "teto", None)
    return escolha, schema.mesa_em_economia(teto)


#: As três dicas do botão, uma por origem (`schema.origem_da_economia`).
ECONOMIA_DICA = {
    None: "Liga a economia de bateria só neste controle.",
    "controle": "A economia de bateria está ligada neste controle. Clique para desligar.",
    "mesa": "A «Bateria longa» da aba Sistema liga a economia em todos os controles.",
}


def campos_da_economia(declaracao: Any, uniq: str) -> dict[str, str]:
    """O estado do botão: `economia` (a classe acende) e `economia-dica`."""
    from hefesto_dualsense4unix.profiles import schema

    escolha, mesa = economia_do_controle(declaracao, uniq)
    origem = schema.origem_da_economia(escolha, mesa)
    return {"economia": "mesa" if origem == "mesa" else ("ligada" if origem else ""),
            "economia-dica": ECONOMIA_DICA[origem]}


def _nomes_dos_donos() -> dict[str, str]:
    """``{endereço: nome}`` pelo dono do nome (o ``Alias`` do BlueZ).

    O nome é do CONTROLE, pelo endereço — o mesmo que a A-CONEXOES lê em
    ``_aparelhos_da_cena``. A leitura é a do fundo (``_em_fundo("bluez")``),
    que o tique da seção do rádio já paga: nenhuma viagem nova ao barramento.
    """
    bluez = _em_fundo("bluez", _ler_o_bluez, 3.0)
    if not bluez:
        return {}
    return _nomes_por_endereco(bluez[1])


def dono_na_linha(nomes: dict[str, str], uniq: str, jogador: Any) -> str:
    """O que o campo do dono mostra: o nome dela, ou «P N» quando não há nome."""
    nome = nomes.get(_mac(uniq), "")
    if nome:
        return nome
    if isinstance(jogador, int) and not isinstance(jogador, bool):
        return f"P{jogador}"
    return ""


_SO_O_NUMERO = re.compile(r"\s*p\s*\d+\s*", re.IGNORECASE)


@gesto("08-conexoes.html", "dono-renomear", grava="escrever_propriedade")
def dono_renomear(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O nome do jogador dono do controle — pelo dono do nome (o `Alias`).

    Apagar o campo, ou deixar só «P N», devolve o nome de fábrica, e a linha
    volta a dizer «P N» (a decisão [02] da aba 01: apagar o nome volta a ele).
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("dono-renomear: o clique não disse em qual controle")
    novo = str(o.get("valor") or "").strip()
    if _SO_O_NUMERO.fullmatch(novo):
        novo = ""
    if novo == _nomes_dos_donos().get(_mac(uniq), ""):
        return
    endereco = _so_hex(uniq)
    if len(endereco) != 12:
        raise RuntimeError(_sem_endereco())
    endereco = ":".join(endereco[i:i + 2] for i in range(0, 12, 2)).upper()
    escrita = _alias_do_aparelho(endereco, novo)
    if not getattr(escrita, "feita", False):
        raise RuntimeError("o Bluetooth do sistema não gravou o nome novo")


@gesto("08-conexoes.html", "economia-do-controle", grava="machine_declare")
def economia_do_controle_gesto(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O botão «Modo Economia de Bateria» da linha — liga ou desliga NESTE controle.

    O dono do que ele faz é a O-MODO-ECONOMIA-POR-CONTROLE-01: a tela só manda
    ``machine.declare`` com ``schema.declaracao_da_economia`` (nunca o
    ``profile.switch``, que é origem manual e trava a troca automática). Sob a
    «Bateria longa» da mesa o botão está aceso pela aba Sistema, e o clique
    aqui não apaga nada: recusa dizendo onde se desliga.
    """
    from hefesto_dualsense4unix.profiles import schema

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("economia-do-controle: o clique não disse em qual controle")
    escolha, mesa = economia_do_controle(_declaracao(), uniq)
    if mesa:
        raise RuntimeError(ECONOMIA_DICA["mesa"])
    corpo = schema.declaracao_da_economia(uniq, escolha is not True)
    ok, motivo = _resposta(p.machine_declare(corpo))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o que você declarou")
    _reler_a_declaracao()


@gesto("08-conexoes.html", "checkup-atualizar")
def checkup_atualizar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Atualizar» do Check-up: relê agora o que a linha de cada controle mostra.

    O «Examinar Entradas» mede as portas (e custa segundos); este botão só
    RELÊ, na hora: a declaração (o microfone e a economia de cada controle),
    os nomes dos donos no BlueZ e o rascunho do mapa das portas. O que ele
    lê o tique seguinte pinta.
    """
    global _LOGICA
    _reler_a_declaracao()
    _esquecer("bluez")
    _LOGICA = None


# ---------------------------------------------------------------------------
# O MAPEAR NUM BOTÃO SÓ — o fluxo guiado porta a porta, pelo dono do mapa
# (`integrations.entrada_a_entrada.o_mapa()`, A-08-UM-MAPEAR-SO-01). Pedido
# dela: *«Use um controle do dualsense (o mesmo), vá de porta em porta
# conectando ele, carrega a informação que medimos, aí ele salva, adiciona um
# nome e adiciona o posicionamento»*. A tela não guarda estado: a foto do dono
# é o estado, e o tique a pinta. <!-- noqa-acento: citação literal dela -->
# ---------------------------------------------------------------------------
#: O que a tela diz em cada estado do fluxo (`foto["estado"]`).
MAPEAR_DIZ = {
    "parado": "Conecte o DualSense por USB numa entrada do computador.",
    "esperando": "Conecte o DualSense por USB numa entrada do computador.",
    "porta": "Entrada encontrada. Dê um nome e o lugar dela, e salve.",
}


def _o_mapa() -> Any:
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee

    return ee.o_mapa()


def html_da_porta_medida(porta: dict[str, Any] | None) -> str:
    """O que o Hefesto mediu da porta da vez, em pares «o quê · valor».

    A lista é de fatos MEDIDOS: a entrada, a velocidade, se está direto no
    computador ou num hub, as quedas dos últimos 7 dias e o lugar que a medição
    deu. O que não foi medido não entra — a linha some, não vira travessão.
    """
    if not porta:
        return '<i class="nada"></i>'
    fatos = [("Entrada", str(porta.get("rotulo") or ""))]
    if porta.get("usb"):
        fatos.append(("Velocidade", f"USB {porta['usb']}"))
    fatos.append(("Ligação", f"num hub ({porta.get('hub_produto') or 'hub'})"
                  if porta.get("hub") else "direto no computador"))
    storm = porta.get("storm")
    if isinstance(storm, int) and not isinstance(storm, bool):
        fatos.append(("Quedas", "nenhuma em 7 dias" if storm == 0
                      else f"{storm} {'queda' if storm == 1 else 'quedas'} em 7 dias"))
    if porta.get("lugar_no_gabinete"):
        fatos.append(("Onde fica", str(porta["lugar_no_gabinete"])))
    pares = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in fatos if v)
    return f'<dl class="mp-fatos">{pares}</dl>'


def html_das_entradas_mapeadas(portas: Any) -> str:
    """As entradas que já têm nome, uma por linha: o nome e o lugar dela."""
    nomeadas = [p for p in (portas or []) if isinstance(p, dict) and p.get("nome")]
    if not nomeadas:
        return '<li class="vazio">Nenhuma ainda.</li>'
    linhas = []
    for porta in nomeadas:
        onde = " · ".join(str(x) for x in (porta.get("rotulo"), porta.get("lugar")) if x)
        linhas.append(f"<li><b>{html.escape(str(porta['nome']))}</b>"
                      f"<span>{html.escape(onde)}</span></li>")
    return "".join(linhas)


def campos_do_mapear(foto: dict[str, Any] | None = None) -> dict[str, str]:
    """Os campos da tela do Mapear, a partir da foto do dono."""
    if foto is None:
        try:
            mapa = _o_mapa()
            foto = mapa.estado()
            if foto.get("estado") != "parado":
                foto = mapa.olhar()
        except Exception:
            foto = {"estado": "parado"}
    estado = str(foto.get("estado") or "parado")
    feitas = foto.get("feitas") or 0
    return {
        "mapear-diz": MAPEAR_DIZ.get(estado, MAPEAR_DIZ["parado"]),
        "mapear-estado": estado,
        "mapear-porta": html_da_porta_medida(foto.get("porta")),
        "mapear-lista": html_das_entradas_mapeadas(foto.get("portas")),
        "mapear-conta": ("Nenhuma entrada salva ainda." if not feitas
                         else f"{feitas} {'entrada salva' if feitas == 1 else 'entradas salvas'}."),
    }


@gesto("08-conexoes.html", "mapear-comecar")
def mapear_comecar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A tela do Mapear abriu: o dono começa a esperar a porta da vez."""
    global _LOGICA
    _LOGICA = None
    _o_mapa().comecar()


@gesto("08-conexoes.html", "mapear-gravar",
       grava="a porta da vez no mapa das portas do maquina.json, pelo dono do mapa")
def mapear_gravar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Salvar esta entrada»: o nome e o lugar da porta da vez, pelo dono.

    `lugar` é a FACE do gabinete (um dos `LUGARES_DA_PORTA`), nunca o lugar D3
    da porta; vazio mantém a face. `ValueError`/`RuntimeError` do dono são a
    recusa dele (nada a gravar, ou não há porta da vez).
    """
    global _LOGICA
    forma = o.get("forma") if isinstance(o.get("forma"), dict) else {}
    nome = str(forma.get("nome") or "").strip() or None
    lugar = str(forma.get("lugar") or "").strip() or None
    _o_mapa().gravar(nome=nome, lugar=lugar)
    # o rascunho velho do gabinete não pode mandar por cima o que o dono gravou
    _LOGICA = None
    _reler_a_declaracao()


@gesto("08-conexoes.html", "mapear-parar")
def mapear_parar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A tela do Mapear fechou: o dono para de olhar as portas."""
    _o_mapa().parar()
