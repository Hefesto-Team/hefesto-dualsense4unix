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
    from hefesto_dualsense4unix.interface.conexoes import Vibracao

#: `state_full` (`radio_ar`, `radio_governador`), que o daemon publica.
SEM_DONO: dict[str, str] = {}


#: que a mudam — ler o disco duas vezes por segundo para pintar dois `<select>`
_DECLARACAO: object | None = None

_MESA_DO_RADIO: object | None = None


#: O que só o exame COMPLETO traz: `pareamentos`, `vizinhanca_das_portas` e as
_EXTRAS: tuple[object, ...] = ()

_ORDENS_NA_TELA: tuple[Any | None, ...] = ()


_DISPENSADAS: dict[str, str] = {}

VOLTA_QUANDO = "se você mudar os cabos"

ORDEM_IGNORADA_VOLTA = f"volta sozinha {VOLTA_QUANDO}"

DICA_DO_IGNORAR = ("Ignora este conselho. Ele fica em cinza na lista e volta "
                   f"sozinho {VOLTA_QUANDO}.")

DICA_DO_DESFAZER = "Traz esta recomendação de volta para a lista."

_EXAME_PEDIDO: bool = False

#: O ``state_full`` do último tique desta aba. O exame completo roda numa
_ULTIMO_ESTADO: dict[str, Any] = {}

_DONGLES: Any = None


def _declaracao(recarregar: bool = False) -> Any:
    """O `maquina.json` já validado (`None` só se o import falhar: `carregar_maquina`"""
    global _DECLARACAO, _SELO_DA_DECLARACAO
    selo = _selo_da_declaracao()
    if _DECLARACAO is None or recarregar or selo != _SELO_DA_DECLARACAO:
        try:
            perfil._com_o_src()
            from hefesto_dualsense4unix.utils.maquina import carregar_maquina

            _DECLARACAO, _SELO_DA_DECLARACAO = carregar_maquina(), selo
        except Exception:
            return None
    return _DECLARACAO


def _mesa_do_radio(recarregar: bool = False) -> Any:
    """Adaptadores e rádios vizinhos, lidos do `/sys` — uma vez, e no botão."""
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
    """Os adaptadores pela ótica do BlueZ — endereço, alias e o nome DO USUÁRIO."""
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


_CENSO: Any = None


def _censo(recarregar: bool = False) -> Any:
    """Tudo que o barramento tem, para o motor julgar as entradas."""
    if recarregar:
        return _ler_o_censo_agora()
    if _CENSO is None:
        _em_fundo("censo", _ler_o_censo_agora, 0.0)
    return _CENSO


def _logica_do_mapa() -> Any:
    """O rascunho do gabinete DO USUÁRIO — `LogicaDoMapa` sobre o que ela declarou."""
    global _LOGICA
    if _LOGICA is None:
        perfil._com_o_src()
        from hefesto_dualsense4unix.interface.logica_do_mapa import LogicaDoMapa
        from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

        declarada = _declaracao()
        mapa = getattr(declarada, "mapa", None) or MapaDaMesa()
        _LOGICA = LogicaDoMapa(mapa)
    return _LOGICA


_LOGICA: Any = None


def esquecer_o_rascunho_do_mapa() -> None:
    """O mapa mudou no disco por outro gesto (o editor do mapa das conexões):"""
    global _LOGICA
    _LOGICA = None
    _reler_a_declaracao()


def _chave_do_radio(r: Any) -> str:
    """`vid:pid` — a chave do `maquina.json`, e não o nó do sysfs."""
    return f"{getattr(r, 'vid', '')}:{getattr(r, 'pid', '')}"


def _tipos_de_radio() -> tuple[dict[str, str], dict[str, str]]:
    """`(rótulo → id, id → rótulo)` das respostas do "— O que é? —"."""
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_mesa import _TIPOS_DE_RADIO

        return ({rotulo: ident for ident, rotulo in _TIPOS_DE_RADIO},
                dict(_TIPOS_DE_RADIO))
    except Exception:
        return {}, {}


def _a_pergunta() -> str:
    """A primeira opção do "— O que é? —" — a pergunta em si."""
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.interface.conexoes import RESPOSTAS_DO_VIZINHO

        return str(RESPOSTAS_DO_VIZINHO[0])
    except Exception:
        return ""


#: ela produz vira uma PERGUNTA na tela (`— Webcam? —`), nunca uma resposta.
#: continua em "— O que é? —", que é a verdade. Sugerir "Wi-Fi" a partir da
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


def _produto_do_no(no: str) -> str:
    """O nome que o aparelho dá de si (o `produto` do censo), ou `""`: é NOME, nunca tipo."""
    censo = _censo()
    aparelho = censo.aparelho(no) if censo is not None and no else None
    return str(getattr(aparelho, "produto", "") or "").strip()


def _e_um_receptor(no: str) -> bool:
    """O censo reconheceu este nó como receptor 2.4G de teclado e mouse?"""
    censo = _censo()
    aparelho = censo.aparelho(no) if censo is not None and no else None
    return bool(getattr(aparelho, "receptor", False))


def _sugestao_do_vizinho(no: str, rotulos: Any) -> str:
    """A palavra da LISTA DO USUÁRIO que o kernel sugere para este rádio, ou `""`."""
    lido = _lido_do_kernel(no)
    if not lido:
        return ""
    if lido in rotulos:
        return lido
    equivale = _SUGESTAO_DO_KERNEL.get(lido, "")
    return equivale if equivale in rotulos else ""


def _moldura_da_pergunta(pergunta: str) -> tuple[str, str]:
    """O «— … —» da pergunta, LIDO dela e não digitado."""
    inicio = 0
    while inicio < len(pergunta) and not pergunta[inicio].isalnum():
        inicio += 1
    fim = len(pergunta)
    while fim > inicio and not pergunta[fim - 1].isalnum():
        fim -= 1
    return pergunta[:inicio], pergunta[fim:]


def _pergunta_sugerida(palavra: str, pergunta: str) -> str:
    """`"— Teclado? —"` — a sugestão vestida de PERGUNTA, nunca de resposta."""
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


#: janela estável tem `("nao_sei", "Não sei")` nas duas perguntas
#: no `machine_declare` — a string `"nao_sei"` faria o pydantic recusar o
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
    pior: um acerto que não vem de leitura nenhuma erra no primeiro clique do usuário.

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

    **A REGRA INVERTEU EM 18/09/2026** (). Antes só `True` contava, e
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
    """`d4:2f:…` → `d42f…` — a forma que o `maquina.json` exige por schema."""
    return norm_mac(uniq) or ""


def _dispensadas_do_disco(declaracao: Any) -> None:
    """Recarrega `{chave: arranjo}` do que o usuário mandou calar."""
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
    """As conferências que cabem NO TIQUE — as três que não forkam processo."""
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
    """O exame COMPLETO uma vez, ao entrar na aba — como a janela estável faz."""
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
    """Esta linha é uma ordem que o usuário mandou calar, **neste arranjo**?"""
    return _ordem_calada(getattr(item, "ordem", None))


def _ordem_calada(ordem: Any) -> bool:
    """A mesma pergunta, feita sobre a ORDEM — é o que o gesto `ignorar` tem na mão."""
    if ordem is None:
        return False
    arranjo = str(getattr(ordem, "arranjo", "") or "")
    return bool(arranjo) and _DISPENSADAS.get(str(ordem.chave)) == arranjo


def _itens_da_tela() -> list[Any]:
    """As linhas do Check-up: as três do tique mais o que o exame completo trouxe."""
    conferidas = _conferencias()
    vistas = {getattr(i, "chave", "") for i in conferidas}
    for item in _EXTRAS:
        chave = getattr(item, "chave", "")
        if chave in vistas:
            continue
        if chave == CHAVE_DA_LEITURA and _o_aviso_do_grab(_ULTIMO_ESTADO) is None:
            continue
        conferidas.append(item)
    # `secao_exame._desenhar_o_que_fazer` a escreve com estas palavras: *"As
    # `teclado_so_no_hub`, ambas `atencao`, medidas nesta  # (noqa-acento) id
    return sorted(conferidas, key=lambda i: getattr(i, "ordem", None) is None)


_SELO_DESCONHECIDO = ("info", "NOTA")

#: e `selo-nao-sei`, e a regra `.selo.grave` do vermelho. Aquela metade da S-09
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
    """A frase do selo quando o estado das LINHAS venceu o do cabeçalho."""
    with contextlib.suppress(Exception):
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.config.secao_exame import FRASE_DO_SELO

        return str(FRASE_DO_SELO.get(estado, ""))
    return ""


def _selo_do_estado(estado: str) -> tuple[str, str]:
    """``(a classe CSS, a palavra)`` do selo — do dono, `interface.conexoes`.

    O MAPA TEM UM DONO e ele já traduzia os quatro estados do `exame_da_mesa`
    para as três palavras que o desenho dela crava. Ele mora na camada de tela
    porque é vocabulário, e não máquina — o próprio módulo do exame diz que
    "responde por máquina, não por vocabulário".

    O IMPORT É TARDIO pela razão de sempre neste arquivo: `interface.conexoes`
    puxa a cadeia de tela, e o topo deste módulo tem de continuar importável
    numa árvore sem `src/` no caminho.

    A PALAVRA DE `problema` AINDA É A DE `atencao` — 02/09/2026, e é  (noqa-acento)
    ESPERA DO USUÁRIO. O mapa do dono manda os dois estados para **AJUSTAR**, e o usuário
    decidiu que *"o que está quebrado agora não pode parecer igual ao que só
    podia estar melhor"*. **A COR já saiu** (ver `selo-estado`, na
    :func:`pacote`, e a regra `.selo.grave` do gerador); a PALAVRA é de produto, e
    trocá-la aqui seria escolher no lugar dela. Quando ela disser, quem muda é
    `interface.conexoes.SELO_DO_ESTADO`, e o mapa é um só.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.interface.conexoes import SELO_DO_ESTADO

    return SELO_DO_ESTADO.get(estado, _SELO_DESCONHECIDO)


def _dica_da_linha(item: Any) -> str:
    """O `?` de uma linha do Check-up, em HTML: o que importa e a cura.

    DUAS METADES, E NÃO TRÊS — decisão, 02/09/2026: *"o ponto de
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
    (`interface.conexoes._e`), o mesmo que o gerador do desenho usa.

    UMA ORDEM DA MESA NÃO TEM VERBETE, E TINHA DE TER O DO USUÁRIO — 02/09/2026, e
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
    `exame_da_mesa.ROTULOS_DA_ORDEM`, *"Por que importa"*
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
        from hefesto_dualsense4unix.integrations.exame_da_mesa import (
            ROTULOS_DA_ORDEM,
        )
        from hefesto_dualsense4unix.interface.conexoes import _e
        from hefesto_dualsense4unix.utils.i18n import _

        chave = str(getattr(item, "chave", ""))
        verbete = DICAS_DAS_LINHAS.get(chave, "")
        if not verbete and chave == CHAVE_DA_LEITURA:
            verbete = _o_porque_e_a_cura_do_dono()[0]
        partes: list[tuple[str, str]] = [("", _(str(verbete)))]
        ordem = getattr(item, "ordem", None)
        if ordem is not None:
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


def _a_entrada_na_frase(numero: str, *, em: bool = False, maiuscula: bool = False) -> str:
    """«a Entrada 3», «na entrada Meio» — o nome pelo dono da leitura e a"""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.entrada_a_entrada import nome_da_entrada
    from hefesto_dualsense4unix.utils.rotulo_da_entrada import com_artigo, na_frase

    declaracao = _declaracao()
    nome = (nome_da_entrada(numero, maquina=declaracao)
            if getattr(declaracao, "mapa", None) is not None else None)
    return com_artigo(na_frase(numero, nome), em=em, maiuscula=maiuscula)


def _a_ordem_na_tela(ordem: Any) -> tuple[str, str]:
    """``(de, para)`` de uma ordem com destino: «Entrada 3» e «Entrada 9», pelo dono do rótulo."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import mapa_das_portas
    from hefesto_dualsense4unix.integrations.entrada_a_entrada import rotulo_do_numero
    from hefesto_dualsense4unix.interface.conexoes import TRACO

    destino = str(getattr(ordem, "destino", "") or "")
    if not destino:
        return "", ""
    caminho = str(getattr(getattr(ordem, "alvo", None), "caminho", "") or "")
    declaracao = _declaracao()
    mapa = getattr(declaracao, "mapa", None)
    numero = mapa_das_portas.porta_de(mapa, caminho) if mapa is not None else None
    dela = declaracao if mapa is not None else None
    de = rotulo_do_numero(numero or "", maquina=dela) or caminho or TRACO
    return de, rotulo_do_numero(destino, maquina=dela) or destino


def _o_movimento_da_central(cena: dict[str, Any] | None) -> Any:
    """A proposta da central (`radio_central.proposta`) como :class:`Movimento`, ou `None`."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import ar_do_adaptador, dicas_da_conexao

    proposta = (cena or {}).get("proposta") or {}
    aparelhos = (cena or {}).get("aparelhos") or ()
    lugares = {str(lug.get("id")): lug for lug in (cena or {}).get("lugares") or ()
               if lug.get("sabido", True)}
    ap = next((a for a in aparelhos if a.get("id") == proposta.get("controle")), None)
    para = lugares.get(str(proposta.get("destino") or ""))
    de = lugares.get(str(ap.get("lugar") or "")) if ap is not None else None
    if ap is None or para is None or de is None:
        return None
    evitados = _evitados_do_lugar(cena or {}, str(de["id"]))
    bons = None if evitados is None else ar_do_adaptador.CANAIS_DO_BT - len(evitados)
    jogador = ap.get("jogador")
    return dicas_da_conexao.Movimento(
        controle=str(ap["id"]),
        jogador=jogador if isinstance(jogador, int) and not isinstance(jogador, bool) else None,
        nome_do_controle=nome_na_conexoes(ap),
        de_id=str(de["id"]), de_nome=_titulo_do_lugar(de),
        para_id=str(para["id"]), para_nome=_titulo_do_lugar(para),
        controles_no_de=sum(1 for a in aparelhos
                            if a.get("lugar") == de.get("id") and a.get("tipo") == "controle"),
        bons=bons,
        sufocado=bons is not None
        and ar_do_adaptador.nivel_dos_canais(bons) == ar_do_adaptador.NIVEL_ENGASGA)


def _perto_de(lug: dict[str, Any]) -> str:
    """«da Entrada 4» pela entrada da caixa; sem entrada numerada, «do adaptador Meio»."""
    entrada = str(lug.get("entrada") or "")
    if entrada.startswith("Entrada "):
        return f"da {entrada}"
    nome = _titulo_do_lugar(lug)
    return f"do adaptador {nome}" if nome and nome != DENTRO_DA_MAQUINA else ""


def _as_dicas_do_pedido(cena: dict[str, Any] | None) -> list[Any]:
    """Um cartão por controle conhecido que pede para parear (``cena["pedindo"]``)."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import dicas_da_conexao

    lugares = {str(lug.get("id")): lug for lug in (cena or {}).get("lugares") or ()}
    return [dicas_da_conexao.dica_do_pedido(
        str(x["aparelho"]), str(x["nome"]), _perto_de(lugares[str(x["lugar"])]), str(x["lugar"]))
        for x in (cena or {}).get("pedindo") or () if str(x.get("lugar")) in lugares]


def _a_dica_do_wifi(cena: dict[str, Any] | None) -> list[Any]:
    """O Wi-Fi que o diário do kernel viu cair: um cartão por rede, com a causa se for conhecida."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import dicas_da_conexao

    saida = []
    vizinhos = list((cena or {}).get("vizinhos") or ())
    for i, rede in enumerate((cena or {}).get("wifi") or ()):
        quem = _id_da_rede(rede, _o_vizinho_da_rede(rede, vizinhos), i)
        usb3 = _usb_da_porta(cena or {}, quem) == "3.0"
        selo, nota, _dica = _a_saude_do_wifi(rede, usb3)
        if selo is None:
            continue
        nivel = (dicas_da_conexao.AJUSTE if selo.nivel == "sofrendo" else dicas_da_conexao.NOTA)
        saida.append(dicas_da_conexao.dica_do_wifi(
            selo.texto, bool(nota), DICA_DO_USB_3_NO_2_4, nivel))
    return saida


def _a_dica_do_receptor(cena: dict[str, Any] | None) -> list[Any]:
    """O receptor 2.4G que sofre: um cartão por receptor cuja saúde passou do aperto."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import dicas_da_conexao

    saida = []
    for viz in (cena or {}).get("vizinhos") or ():
        if not viz.get("receptor"):
            continue
        tipo = str(viz.get("tipo") or viz.get("sugestao_tipo") or "")
        selo = receptor_sem_fio.selo_da_saude(viz.get("saude"), tipo)
        if selo is not None and selo[0] == "sofrendo":
            saida.append(dicas_da_conexao.dica_do_receptor(tipo, selo[1], selo[2]))
    return saida


def _a_cura(texto: str) -> str:
    """«O que fazer: …» pela frase do dono (`secao_exame.PREFIXO_DA_CURA`); vazio sem texto."""
    if not texto.strip():
        return ""
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_exame import PREFIXO_DA_CURA

    return PREFIXO_DA_CURA + texto.strip()


def _o_painel_das_dicas(vivos: list[Any], cena: dict[str, Any] | None) -> Any:
    """As dicas da aba: o movimento da central, o Wi-Fi que cai e cada achado do exame.

    Cada ``Item`` do exame vira um cartão (ou, se deu certo, uma palavra da linha «✓ …»); a ordem
    que ela calou continua, apagada e no fim, com o mesmo botão para voltar a mostrá-la.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import dicas_da_conexao as dicas

    cartoes: list[Any] = list(_as_dicas_do_pedido(cena))
    certos: list[str] = []
    movimento = _o_movimento_da_central(cena)
    if movimento is not None:
        cartoes.append(dicas.dica_do_movimento(movimento))
    cartoes += _a_dica_do_wifi(cena)
    cartoes += _a_dica_do_receptor(cena)
    for slot, item in enumerate(vivos):
        estado = str(getattr(item, "estado", "") or "")
        chave = str(getattr(item, "chave", "") or "")
        ordem = getattr(item, "ordem", None)
        if estado == "certo":
            certos.append(dicas.o_que_esta_certo(chave, str(getattr(item, "rotulo", "") or "")))
        elif ordem is not None:
            de, para = _a_ordem_na_tela(ordem)
            cartoes.append(dicas.dica_da_ordem(
                ordem, estado, slot=slot, calada=_ordem_calada(ordem), de=de, para=para,
                cura=_a_cura(str(getattr(ordem, "acao", "") or "")),  # (noqa-acento): campo
                dica_de_ignorar=DICA_DO_IGNORAR, dica_de_voltar=DICA_DO_DESFAZER))
        else:
            cartoes.append(dicas.dica_da_conferencia(
                chave, str(getattr(item, "rotulo", "") or ""), estado,
                str(getattr(item, "porque", "") or ""),
                cura=_a_cura(str(getattr(item, "cura", "") or ""))))
    return dicas.montar(cartoes, certos)


def _html_das_dicas(vivos: list[Any] | None = None, cena: dict[str, Any] | None = None) -> str:
    """As dicas inteiras, em HTML: o que o ``data-campo="dicas"`` repinta a cada tique.

    Sem ``vivos`` (a bancada, os testes) saem as ordens que o tique pintou por último.
    """
    from hefesto_dualsense4unix.interface.conexoes import html_das_dicas

    if vivos is None:
        vivos = [_ItemDeOrdem(o) for o in _ORDENS_NA_TELA if o is not None]
    return html_das_dicas(_o_painel_das_dicas(vivos, cena), icone_da_dica)


@_dataclasses.dataclass(frozen=True)
class _ItemDeOrdem:
    """Uma ordem sozinha na forma de ``Item`` — o que a bancada e as réguas entregam."""

    ordem: Any
    estado: str = "atencao"  # (noqa-acento): chave de máquina do exame
    chave: str = ""
    rotulo: str = ""
    porque: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "chave", str(getattr(self.ordem, "chave", "")))


def _monta() -> Any:
    """O módulo `interface/monta.py`, importável de dentro do pacote."""
    import sys

    from hefesto_dualsense4unix.interface import onde as _onde

    sys.modules.setdefault("onde", _onde)
    from hefesto_dualsense4unix.interface import monta

    return monta


def _leitura_das_ordens_da_maquina(declaracao: Any) -> Any:
    """O `leitura_das_ordens` do exame: com a declaração, a do exame da janela"""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import leitura_das_ordens
    from hefesto_dualsense4unix.integrations import exame_da_mesa

    if declaracao is None:
        return exame_da_mesa.leitura_do_sistema

    return lambda: leitura_das_ordens(declaracao)


def _linha(item: Any) -> dict[str, Any]:
    """Um `Item` do exame na forma que a tela consome.

    OS CAMPOS SÃO `rotulo`, `estado` e `porque` — os do `exame_da_mesa.Item`,
    lidos do dataclass. A primeira versão daqui pedia `titulo` com `or str(it)`
    de reserva, e o `Item` não tem `titulo`: a reserva ganhava sempre e o
    **`repr` do objeto Python foi parar na tela do usuário**, visível na foto de
    01/09 — `Item(chave='energia_do_radio', rotulo='Economia de energia
    desligada', estado='a`, cortado no meio.

    Um `getattr` com reserva é o disfarce perfeito para um campo que não existe:
    ele não levanta, e o que sai parece dado.

    A PALAVRA DO SELO E A DICA SÃO DO PRODUTO — 02/09/2026. Antes, o pacote
    montava as duas à mão, e as duas erravam:

    * o selo saía de um `"AJUSTAR" if grave else "CERTO"`, e o `Item` tem
      QUATRO estados. `interface.conexoes.SELO_DO_ESTADO` os mapeia em TRÊS
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
        "selo": _selo_do_estado(estado)[1],
        "classe": _selo_do_estado(estado)[0],
        "dica": _dica_da_linha(item),
        # (`ajustar`, `atencao`) são achados de verdade.  # (noqa-acento) id
        "grave": estado.lower() not in {"certo", ""},
        "ordem": "" if ordem is None else str(ordem.chave),
        "arranjo": "" if ordem is None else str(ordem.arranjo),
        "calada": "sim" if _calada(item) else "",
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

    **A LEITURA DOS CONTROLES TAMBÉM NÃO ATRAVESSA — 28/09/2026.** A aba Jogar
    já diz esse fato pelo dono dele (`painel.aviso_do_grab_dobrado`, com a
    mesma condição de `home_actions.aviso_de_grab`); a linha desta aba só
    acrescenta a causa, e duas contagens do mesmo aviso lá divergiriam.
    """
    return [_linha(i) for i in _itens_da_tela()
            if not _calada(i) and getattr(i, "chave", "") != CHAVE_DA_LEITURA]


def _bancada() -> Any:
    """A mesa do motor montada sobre o rascunho DO USUÁRIO — ou `None` sem censo."""
    censo = _censo()
    if censo is None:
        return None
    perfil._com_o_src()
    from hefesto_dualsense4unix.interface.logica_do_mapa import bancada_do_rascunho

    with contextlib.suppress(Exception):
        return bancada_do_rascunho(_logica_do_mapa(), censo)
    return None


PALAVRA_DA_CONTA = {0: "nada", 1: "uma coisa", 2: "duas coisas", 3: "três coisas",
                    4: "quatro coisas", 5: "cinco coisas"}

ROTULO_DA_CONTA = "Sem conferir neste desenho:"


def palavra_da_conta(quantas: int) -> str:
    """`3` → "três coisas". Fora da tabela, o número cru — nunca uma palavra errada."""
    return PALAVRA_DA_CONTA.get(int(quantas), str(int(quantas)))


def _confissao_do_mapa() -> dict[str, str]:
    """Os campos da confissão — o que o desenho DO USUÁRIO não consegue conferir.

    O DONO DAS FRASES É `mapa_da_mesa.confissao_do_desenho`, o mesmo que a
    janela do desenho redesenha a cada mudança. Aqui só a CONTA vai à tela, por
    extenso, depois de :data:`ROTULO_DA_CONTA`. **Os itens saíram do `title` em
    13/09/2026** (FRASES-E-DICAS-02): eram confissão em primeira pessoa numa
    dica flutuante, e continuam no `?` do topo da tela do mapa, que é ajuda.

    O DEFEITO QUE ISTO FECHA, medido nesta bancada em 03/09/2026: a
    `.mm-conf-linha` está FORA do bloco `.mm-faces` que o pacote troca, então
    ninguém nunca a repintava. Ela dizia **"três coisas"** — a conta da cena do
    mockup — e o `title` listava as três; a bancada tem **UMA** lacuna
    (`especie`). Uma confissão que confessa a mais é tão falsa quanto uma que
    cala: manda ela procurar duas coisas que o produto já sabe.

    `confissao-nada` É O INTERRUPTOR DO SUMIÇO, e a regra é da GTK: lá a linha
    SOME quando o desenho responde por tudo (`confissao_do_desenho` devolve
    vazio e o `_desenhar` não escreve nada). Sem ele, zero lacuna viraria  — uma frase que ocupa
    espaço para não dizer nada.

    O DICIONÁRIO VAZIO É RESPOSTA, e é por isso que esta função não devolve
    tupla: sem censo o pacote não sabe quantas lacunas há, e emitir `""` seria
    PIOR que não emitir — o `escrever()` do piloto troca vazio por travessão, e
    a tela diria . Não
    emitir deixa a linha como o desenho a escreveu, que é o único estado
    honesto quando a leitura do barramento falhou.
    """
    bancada = _bancada()
    if bancada is None:
        return {}
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.interface.logica_do_mapa import (
            confissao_do_desenho,
        )

        itens = tuple(confissao_do_desenho(bancada))
    except Exception:
        return {}
    if not itens:
        return {"confissao-nada": "sim", "confissao-conta": palavra_da_conta(0)}
    return {"confissao-nada": "",
            "confissao-conta": palavra_da_conta(len(itens))}


def _html_do_mapa() -> str:
    """As faces do gabinete DO USUÁRIO, desenhadas pelo produto.

    O DESENHO É UM SÓ (`interface/conexoes.html_do_mapa`) e o gerador do mockup
    usa o MESMO — a diferença é o dado: lá é a cena de bancada, aqui é o que ela
    declarou. Foi assim que a extração se provou fiel: a página regerada saiu
    byte a byte igual à que o usuário aprovou.

    O VEREDITO VEM DO MOTOR, e não de uma cópia: `veredito_do_quadrado` chama
    `arranjo_da_mesa.julgar`, que sabe de entrada azul, de folga na fileira e de
    extensor — e CONFESSA o que não sabe. O gerador tinha uma reescrita à mão
    disso, com os cinco vereditos digitados.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.interface import conexoes as _tela
    from hefesto_dualsense4unix.interface import logica_do_mapa as mm

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
    """O que o censo achou — o PRIMEIRO tempo do gesto de dois tempos."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.interface import logica_do_mapa as mm
    from hefesto_dualsense4unix.interface.conexoes import _e

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
        dica = (mm.DICA_JA_COLOCADO.format(onde=_a_entrada_na_frase(em, em=True))
                if em else "")
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

    **A LISTA MORA DENTRO DA MOLDURA `.gc` — escolha, 06/09/2026.** A
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

        `interface.conexoes._e` é exatamente esta linha, e importá-lo seria uma
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
        fora.append(
            '<div class="ext-linha">'
            f'<span class="ext-nome">{_e(_format_external_title(entrada))}</span>'
            f'<span class="ext-via">{_e(_format_external_subtitle(entrada))}</span>'
            f'{linha_do_aviso}</div>')
    return "".join(fora)


SEM_NOME = "Sem nome"

RENOMEAR_DICA = (
    "Duplo clique para dar um nome a este adaptador — «Sala», «Extra». "
    "O resto da tela passa a usá-lo."
)


# AS TRÊS FUNÇÕES ABAIXO TÊM DOIS CHAMADORES E UM DONO, e é o molde que a
# `a04_iluminacao.um_botao_de_player` já provou: o gerador `aba08.py` as chama
def _cor_desconhecida() -> str:
    from hefesto_dualsense4unix.interface import mesa_viva

    return mesa_viva.COR_DESCONHECIDA


def rotulo_do_controle(c: Any, completo: bool = True) -> str:
    """A ordem, 26/08: marca • player • plástico • transporte."""
    marca = 'Sony <span class="pt">•</span> ' if completo else ""
    jogador = f'Player {c["jogador"]}' if completo else f'P{c["jogador"]}'
    nome = str(c.get("nome") or "")
    plastico = (f'{nome} <span class="pt">•</span> '
                if nome and nome != _cor_desconhecida() else "")
    return f'{marca}{jogador} <span class="pt">•</span> {plastico}{c["via"]}'


def rotulo_curto_do_controle(c: Any) -> str:
    """«Cosmic Red • USB» — o rótulo da linha do Check-up, sem a marca e sem o jogador."""
    nome = str(c.get("nome") or "")
    plastico = (f'{nome} <span class="pt">•</span> '
                if nome and nome != _cor_desconhecida() else "")
    return f'{plastico}{c.get("via") or ""}'


#: porque a folha dela pinta o ponto mais apagado que o texto em volta. As duas
_PONTO = ' <span class="pt">•</span> '


#: DERIVADO do transporte. Pelo CABO o DualSense expõe placa USB Audio própria e
_CAMINHO_DO_MIC = {"bt": ("pelo BT", "Pela ponte"),
                   "usb": ("pelo USB", "Placa do controle")}


def caminho_do_microfone(via: str) -> str:
    """*"pelo BT • Pela ponte"* ou *"pelo USB • Placa do controle"*."""
    chave = (via or "").strip().lower()
    rota, quem = _CAMINHO_DO_MIC.get(chave, _CAMINHO_DO_MIC["usb"])
    return f"{rota}{_PONTO}{quem}"


#: Pelo cabo o DualSense expõe uma placa USB Audio própria (medido em
#: **O QUE ELA NÃO DIZ MAIS**, e é a correção de 04/09: nenhuma das duas
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


LUZ_TRAVADA = "cabo"
LUZ_LIVRE = "radio"  # (noqa-acento) valor de atributo, ASCII por contrato


def trava_da_luz(via: str) -> str:
    """`"cabo"` quando o botão da luz não tem o que fazer; `"radio"` quando tem."""
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
       era aviso com instrução: a ordem de 13/09 tira frase de aviso da
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
    o registro «A-TERCEIRA-LISTA-DELA-INDICE» de 13/09/2026.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        dica_do_botao,
    )

    no_radio = trava_da_luz(via) == LUZ_LIVRE
    dados = _dataclasses.make_dataclass(
        "ControleDaLuz", ["adotado", "no_cabo", "uniq"])(True, not no_radio, "x")
    return dica_do_botao(dados)


# piloto: o tique é de 100 ms (`hefesto_vivo.TIQUE_MS`) e a espera conta

_ESPERAS: dict[str, _EsperaNaTela] = {}


class _EsperaNaTela:
    """Uma espera pelo PS, com o relógio por fora."""

    def __init__(self, espera: Any, agora: float) -> None:
        self.espera = espera
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
            print(f"[relato] {PAGINA} · luz-nao-acende: {porque}", file=sys.stderr)


def _agora() -> float:
    """O relógio da espera. MONOTÔNICO — ver o cabeçalho desta seção."""
    return time.monotonic()


def comecar_a_espera(uniq: str, *, agora: float | None = None,
                     sonda: Any = None) -> Any:
    """O controle caiu do rádio; a tela entra no estado 2 do desenho."""
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
    """Ela desistiu. `True` quando havia espera a cancelar."""
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
    """Um passo do relógio, UMA vez por tique, para todas as esperas vivas."""
    quando = _agora() if agora is None else agora
    for chave, dele in list(_ESPERAS.items()):
        dele.correr(quando)
        if not dele.contando and _ESPERAS.get(chave) is dele:
            _ESPERAS.pop(chave, None)


def texto_do_botao_da_luz(uniq: str = "") -> str:
    """O rótulo do botão: `"A luz não acende"`, ou `"Cancelar"` na espera."""
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


#: A recusa estava registrada em `SEM_GESTO` e só aparecia no terminal, a cada
FALA_DO_BOTAO_DO_MIC = {
    True: "O computador inteiro",
    False: "Só este controle",
}


def escopo_do_botao_do_mic(estado: Any) -> str:
    """O que o botão FÍSICO do microfone cala — lido do daemon, um por máquina.

    A chave é `mic_button_toggles_system`, publicada pelo `state_full` desde o
    `MIC-EXPOSE-01` (*"o botão de mic deixa de ser campo secreto do lifecycle —
    a GUI/CLI leem o estado efetivo daqui"*). Medido na máquina do usuário em
    04/09/2026: `True`.

    AUSÊNCIA DEVOLVE VAZIO, e não o padrão do `DaemonConfig`: um daemon que não
    respondeu não é um daemon que respondeu `True`. O `escrever()` do piloto
    traduz vazio em travessão, que é a resposta honesta.
    """
    valor = (estado or {}).get("mic_button_toggles_system")
    return "" if valor is None else FALA_DO_BOTAO_DO_MIC[bool(valor)]


def _texto_da_bateria(bruto: Any) -> str:
    """`100%`, ou o travessão do produto quando ninguém leu.

    O DONO É `interface.conexoes.Controle.texto_da_bateria`, e é ele que decide
    que a ausência vira **travessão** e não zero: *"sem fonte, escreve `— %` em
    vez de um número herdado"* é a regra que a janela estável já segue
    (`status_actions._set_battery_text`).

    O `Controle` É CONSTRUÍDO SÓ PARA ISSO, com os outros campos no valor
    neutro, e é de propósito: a alternativa era escrever `f"{n}%"` aqui, que é a
    segunda grafia da mesma regra — e a primeira coisa que se perde numa segunda
    grafia é justamente o caso do `None`.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.interface.conexoes import Controle

    n = int(bruto) if isinstance(bruto, int | float) else None
    return Controle(uniq="", jogador=0, via="", bateria=n).texto_da_bateria


def _hex_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, ou `""` quando ninguém leu a cor."""
    if not slug:
        return ""
    try:
        import monta

        cor = str(monta.cor_da_zona(slug))
    except Exception:
        return ""
    return cor if re.fullmatch(r"#[0-9a-fA-F]{6}", cor) else ""


def colorway_do_controle(m: Any) -> str:
    """O modelo do mapa dela para aquele controle, ou `""` quando ninguém leu."""
    return str(m.get("cor") or "")


# de 2»), e o que não cabe vira o pedido do governador (`radio_governador`).

# A CADEIA JÁ EXISTIA INTEIRA, e nada dela é desta leva. O que faltava era a


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
    corpo dela. Reler o arquivo a cada tique não traria informação nova.
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

    `vibracao` é a `interface.conexoes.Vibracao` com o que vale para a mesa
    INTEIRA — o global do perfil, o global VIVO do daemon e o orçamento —, e
    esta função só lhe acrescenta o override desta peça. Os três eram um
    argumento `orcamento` só até 01/09/2026, e a tela reportava o errado: o `?`
    dizia *"o global vale Sem teto"* enquanto o daemon cortava a 0,3.

    A CHAVE É O `uniq` NORMALIZADO — doze hexa minúsculos sem separador, e a
    normalização é do :func:`_so_hex` deste arquivo, nunca escrita de novo. É o
    que `Profile._validate_controllers_keys` canoniza ao carregar
    (`profiles/schema.py:1392`), logo é o que está no disco; procurar por
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
    (`interface.conexoes.rotulo_da_politica` diz por quê). Um perfil escrito pela
    janela estável — `app/actions/rumble_actions.py` — ou editado à mão
    guarda uma das outras três.

    FATO SUBSTITUÍDO — 19/09/2026. Aqui estava: *"Medido em 01/09/2026: zero dos
    33 perfis do usuário têm `controllers[*].rumble`, então o caso é hoje
    inalcançável"*. **Deixou de ser verdade, e o próprio arquivo já dizia**: o
    bloco de :3183, remedido em 17/09 pela VIBRA-ACESA-01, conta 5 perfis com
    override por controle. Duas afirmações opostas no mesmo arquivo obrigam
    quem lê a escolher, que é o defeito que a regra do fato-substituído existe
    para matar.

    **Remedido no disco do usuário em 19/09/2026, e o número CRESCEU de novo:**

        29 perfis
         6 com override de rumble por controle  ·  11 entradas
         5 com override de gatilho              ·  10 entradas

    O caso **é alcançável hoje**, e por isso continua tendo de estar escrito —
    a razão da nota não mudou, só o fato que a sustentava.
    """
    from hefesto_dualsense4unix.interface import conexoes as _tela

    chave = _so_hex(uniq)
    dele = overrides.get(chave) or overrides.get(uniq) or {}
    seu = (dele.get("rumble") or {}) if isinstance(dele, dict) else {}
    policy = seu.get("policy") if isinstance(seu, dict) else None
    v = _dataclasses.replace(vibracao, do_controle=policy)
    campo, _ = _tela.teto_que_vale(v)
    frase = _tela.dica_do_teto(v)
    if campo is None:
        sem_dono[f"controle.{chave}.vibracao.teto"] = (
            f"o perfil guarda a política {policy!r} para este controle, e o "
            f"campo desta tela só sabe mostrar {list(_tela.opcoes_do_teto())}. "
            f"Escolher uma das três seria a tela afirmar um estado que o disco "
            f"contradiz — o `?` ao lado diz o que há, e a caixa fica parada.")
    return campo, frase


# `controller.target.set`, o daemon obedece, e no tique seguinte a tela
# aba. Substituído no lugar, e não guardado ao lado.
TODOS_NA_TELA = "todos"


def _pref_do_alvo(ctx: Contexto) -> str:
    """Qual lugar da mesa a saída está mirando — `p1`..`p4`, ou `todos`.

    **A CONVERSÃO É O PONTO INTEIRO, e ela tem duas ordens diferentes.** O
    daemon guarda `output_target_index`, que é a POSIÇÃO em `controllers`
    ("0 = primário", `ipc_handlers.py:3829`); o desenho endereça por `pref`, que
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


# primeiros vêm do `state_full` pelos donos de `app/actions/`, e os dois
def _sem_valor() -> str:
    """`monta.NADA_A_DIZER` — o marcador que faz a `.ressalva` SUMIR."""
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


_ENTRADAS: Any = None
_GABINETE: Any = None


def _entradas(recarregar: bool = False) -> Any:
    """Os nós de entrada do gabinete, **inclusive os vazios** — ou `()`."""
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
    """O `gabinete.json` que o install gravou — `{}` quando não há."""
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


TIQUE_LENTO_DA_08_MS = 50.0
_COLETA = [0.0]
_COMECO_DA_COLETA: dict[int, float] = {}


def _olho_da_coleta(fase: str, _info: dict[str, Any]) -> None:
    """``gc.callbacks``: soma o tempo de cada coleta, em qualquer fio."""
    if fase == "start":
        _COMECO_DA_COLETA[threading.get_ident()] = time.perf_counter()
        return
    comeco = _COMECO_DA_COLETA.pop(threading.get_ident(), None)
    if comeco is not None:
        _COLETA[0] += time.perf_counter() - comeco


class _MedidaDoTique:
    """O relógio do :func:`pacote` e das partes dele — e a linha ``[08 lento]``."""

    PARTES = ("rádio", "exame", "mapa", "gestão")

    def __init__(self) -> None:
        self.partes: dict[str, float] = {}
        self.total = self.cpu = self.coleta = 0.0
        self._marcas = (0.0, 0.0, 0.0)

    def __enter__(self) -> _MedidaDoTique:
        import gc

        if _olho_da_coleta not in gc.callbacks:
            gc.callbacks.append(_olho_da_coleta)
        self._marcas = (time.perf_counter(), time.thread_time(), _COLETA[0])
        return self

    def __exit__(self, *_erro: object) -> None:
        parede, cpu, coleta = self._marcas
        self.total = (time.perf_counter() - parede) * 1000
        self.cpu = (time.thread_time() - cpu) * 1000
        self.coleta = (_COLETA[0] - coleta) * 1000

    def somar(self, nome: str, desde: float) -> None:
        """Soma à parte ``nome`` o tempo desde ``desde`` (``time.perf_counter``)."""
        self.partes[nome] = self.partes.get(nome, 0.0) + (time.perf_counter() - desde) * 1000

    @contextlib.contextmanager
    def parte(self, nome: str) -> Any:
        comeco = time.perf_counter()
        try:
            yield
        finally:
            self.somar(nome, comeco)

    def linha(self) -> str:
        """``[08 lento] 312 ms · cpu 20 · rádio 12 · exame 3 · mapa 2 · gestão 4 · resto 11"""
        partes = [f"{nome} {round(self.partes.get(nome, 0.0))}" for nome in self.PARTES]
        resto = max(0.0, self.total - sum(self.partes.values()))
        return " · ".join([f"[08 lento] {round(self.total)} ms", f"cpu {round(self.cpu)}",
                           *partes, f"resto {round(resto)}", f"coleta {round(self.coleta)}"])

    def dizer(self) -> None:
        """A linha vai ao ``stderr`` da janela (o ``interface.log``), logo antes"""
        if self.total > TIQUE_LENTO_DA_08_MS:
            print(self.linha(), file=sys.stderr, flush=True)


@registrar("08-conexoes.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """O tique da 08, medido por partes (:class:`_MedidaDoTique`)."""
    with _MedidaDoTique() as medida:
        campos = _o_pacote(ctx, medida)
    medida.dizer()
    return campos


def _o_pacote(ctx: Contexto, medida: _MedidaDoTique) -> dict[str, Any]:
    global _ORDENS_NA_TELA, _ULTIMO_ESTADO
    st = ctx.state
    _ULTIMO_ESTADO = st if isinstance(st, dict) else {}
    _pedir_o_exame_de_entrada()
    with medida.parte("exame"):
        vivos = _itens_da_tela()
    _ORDENS_NA_TELA = tuple(getattr(i, "ordem", None) for i in vivos)

    declaracao = _declaracao()

    #
    # abriria os mesmos arquivos quatro vezes por tique. A viva vem do `state`
    perfil_ativo = perfil.ativo(st.get("active_profile"))
    overrides = (perfil_ativo.get("controllers") or {}) if perfil_ativo else {}
    global_do_perfil = ((perfil_ativo.get("rumble") or {}).get("policy")
                        if perfil_ativo else None)
    orcamento, mesa_respondeu = _orcamento_da_mesa()
    from hefesto_dualsense4unix.interface.conexoes import Vibracao

    vibracao = Vibracao(
        do_perfil=global_do_perfil,
        a_viva=st.get("rumble_policy"),
        orcamento=orcamento,
        a_mesa_respondeu=mesa_respondeu,
    )
    sem_dono: dict[str, str] = {}

    da_mesa = {str(m.get("uniq") or ""): m for m in ctx.mesa}

    _correr_as_esperas()

    nomes = _nomes_dos_donos()
    modo_da_mesa: str | None = None
    colunas = {}
    comeco_da_gestao = time.perf_counter()
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        teto_campo, teto_frase = _teto_do_controle(overrides, uniq, vibracao, sem_dono)
        eu = da_mesa.get(uniq) or {}
        colunas[uniq] = {
            "via": (c.get("transport") or "").upper(),
            # A BATERIA COMO A TELA A ESCREVE — `Controle.texto_da_bateria`, o
            # ninguém leu em vez de um número herdado. Ela era o `battery_pct`
            "bateria": _texto_da_bateria(c.get("battery_pct")),
            "nome": (nome_com_a_bateria(rotulo_curto_do_controle(eu), c.get("battery_pct"))
                     if eu else ""),
            "plastico": _hex_do_plastico(str(eu.get("cor") or "")),
            "desenho": colorway_do_controle(eu),
            "ponte": bool(c.get("uniq") in (st.get("pontes_confirmadas") or {})),
            "fragil": bool(c.get("uniq") in (st.get("native_bt_fragil_controles") or [])),
            "mic-existe": "Ligado" if _mic_declarado(declaracao, uniq) else "Desligado",
            # DESLIGADA no `maquina.json` dela (medido em 03/09), a tela
            "mic-caminho": caminho_do_microfone(str(c.get("transport") or "")),
            # nascia apagado no P1 e aceso no P2 porque foi assim que o mockup
            "luz-trava": trava_da_luz(str(c.get("transport") or "")),
            # o `nascimento` do `state_full` fica para o diagnóstico.
            "luz-dica": dica_da_luz(str(c.get("transport") or "")),
            "luz-texto": texto_do_botao_da_luz(uniq),
            "luz-espera": linha_da_espera(uniq),
            # O `title` DA LINHA DO MICROFONE — ver :func:`dica_do_microfone`. O
            "mic-dica": dica_do_microfone(str(c.get("transport") or "")),
            "teto-explica": teto_frase,
        }
        if teto_campo is not None:
            colunas[uniq]["teto-da-vibracao"] = teto_campo
        if modo_da_mesa is None:
            modo_da_mesa = modo_da_fileira(st)
        colunas[uniq].update(estado_do_controle(c, eu, st, declaracao, modo_da_mesa))
        colunas[uniq].update(perfil_na_linha(declaracao, uniq))
        colunas[uniq]["dono"] = dono_na_linha(nomes, uniq, eu.get("jogador"))
    medida.somar("gestão", comeco_da_gestao)
    confissao = _confissao_do_mapa()
    with medida.parte("rádio"):
        radio = campos_do_radio(ctx)
    with medida.parte("mapa"):
        mapa = _html_do_mapa()
    return {
        **campos_do_mapear(),
        "colunas": colunas,
        "blocos": {".mm-faces": mapa},
        "aparelhos": _html_dos_aparelhos(),
        **confissao,
        "dicas": _html_das_dicas(vivos, _CENA_NA_TELA),
        # pelo «Examinar Entradas». (noqa-acento: citação literal)
        **_sala_na_tela(declaracao),
        "externos-lista": _html_dos_externos(ctx),
        "mic-escopo": escopo_do_botao_do_mic(st),
        **radio,
        "alvo-aberto": _alvo_de_saida(ctx),
        #
        # (`status_actions.texto_de_controle_nao_adotado`).
        "sem-driver": _frase_do_sem_driver(st),
        "radio-fragil": _frase_do_radio_fragil(st),
        "sem_dono": sem_dono,
        # que o `alvo-aberto` marca — as ressalvas contam mesmo caladas, porque
        "cobertura": {"pintados": 1 + 2 + 5 + len(confissao)
                      + 1 + 12
                      + sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO) + len(sem_dono)},
    }


#      a trava de `mic-existe` e `vizinho-o-que-e`, e os dois estão ligados.
#      (`Disconnect` do BlueZ por D-Bus, `integrations/gesto_de_reconexao.py`).
#      **Foi exatamente essa a cura de `vizinho-o-que-e`**: em vez de ligar o
from . import gesto  # noqa: E402
from .a02_controles import mudo as _o_mudo_da_aba_02  # noqa: E402

# `integrations/gesto_de_reconexao.py`, que roda `busctl` e não passa pelo
# de quem faça. O `gesto_de_reconexao` faz, é puro, mascara o endereço e devolve
SEM_GESTO: dict[str, str] = {
    # (`interface/conexoes.html_do_mapa`) e o motor de verdade
    # (`arranjo_da_mesa.julgar`, pelo `veredito_do_quadrado`). Com alvo real, os
    "novo-hub":
        "ele é o único dos sete que sobra, e por duas razões que não são de "
        "desenho. A primeira: `LogicaDoMapa` não tem `acrescentar_hub` — um hub "
        "de bancada não é entrada do gabinete, e o produto não tem campo para "
        "ele. A segunda está no próprio `title` do botão: ele promete "
        "*\"pergunta em que entrada ele está ligado\"*, e a tela não tem onde "
        "perguntar. Pendurá-lo no `acrescentar_extensao` faria o botão criar uma "
        "filha numa entrada que ela não escolheu.",
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
    """O `uniq` do controle onde o usuário clicou. Vazio = clique solto, e recusa."""
    return str(o.get("uniq") or "")


def _indice(ctx: Contexto, uniq: str) -> int | None:
    """A posição daquele controle em `controllers` — o que o daemon numera.

    **NÃO é o número do jogador.** `controller.target.set` pede `index`, "posição
    em `controllers`, 0 = primário" (`ipc_handlers.py:3829`), e o próprio produto
    já separa as duas coisas: `status_actions._controller_target_rows:1579` ORDENA
    a lista pelo número de identidade e CARREGA em cada linha o `index` da
    enumeração, com o comentário dizendo por quê — *"a usuária clicaria no chip do
    1 e editaria outro controle"*.

    O `index` vem publicado por entrada (é o mesmo campo que
    `ipc_handlers._numero_de_exibicao:526` lê). Quando ele falta, a posição na
    lista `controllers` é a MESMA conta — e `None` quando nem isso: aí o gesto
    recusa dizendo, em vez de mirar o 0 e trocar o controle do usuário.
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

    DECISÃO, 01/09/2026: **clicar já aplica** — a interface nova não junta
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

    COM O HEFESTO DESLIGADO, A RESPOSTA DESCE AO DISCO — 28/09/2026. A ponte
    devolve `(False, None)` quando o serviço não respondeu, e até aqui o gesto
    recusava: a altura da antena, a visada e o nome de um vizinho se perdiam
    com o serviço parado, sobre um arquivo que não depende dele. Quem grava sem
    serviço é `lugar_declarado.declarar_a_mesa`, a porta da seção `mesa`, com o
    mesmo lock e a mesma fusão do daemon (`gravar_rascunho_da_mesa`), e ele lê
    o arquivo ao ligar. O mesmo desvio do «Aplicar» do rodapé
    (`footer_actions._gravar_declaracao_de_maquina`): só quando o serviço NÃO
    respondeu. Um serviço que respondeu e recusou continua recusando — gravar
    por trás dele deixaria a memória dele divergindo do arquivo.
    """
    ok, motivo = _resposta(p.machine_declare({"mesa": mesa}))
    if ok:
        return
    if not motivo:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_mesa

        if declarar_a_mesa(mesa).gravou:
            return
    raise RuntimeError(motivo or "não consegui gravar o que você declarou")


@gesto("08-conexoes.html", "alvo")
def alvo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Só este": as ações de saída passam a mirar SÓ este controle.

    É o que a própria tela promete no `title` do número e do aparelho de cada
    cartão: *"Escolhe só este controle: a luz, os gatilhos e a vibração passam
    a mirar nele. A fita do topo passa a apontar para ele."*

    `controller.target.set` é exatamente isso, e o handler diz com todas as
    letras (`daemon/ipc_handlers.py:3833`): *"Com o alvo setado,
    lightbar/gatilhos/player-LED/rumble/mic-LED passam a mirar SÓ aquele
    controle"*. É o mesmo método que o seletor da GUI estável chama
    (`app/actions/status_actions.py`).

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
    (`ipc_handlers.py:3905-3906`: *"`index` null volta ao broadcast (padrão)"*), e é o
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
    DECLARADA: `MesaDeclarada.altura_da_antena` (`utils/maquina.py:141`), que só
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

    O par da de cima: `MesaDeclarada.linha_de_visada` (`utils/maquina.py:150`),
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
    """A chave deste controle no `maquina.json` — doze hexa, ou `""`."""
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
        return ("Este controle não tem endereço fixo, e sem ele não há onde "
                "guardar a ponte do microfone.")


def _slot(o: dict[str, Any], quantos: int, quem: str) -> int:
    """A POSIÇÃO em que o usuário clicou, conferida contra o que foi pintado."""
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
    (`utils/maquina.py:522`), decisão de 22/08/2026 (*"por controle"*).

    QUEM CONSOME, e é por isso que o clique vale AGORA: o
    `_handle_machine_declare` relê o disco, rebinda `daemon._maquina` e SOBE OU
    DESCE o subsystem `bt_mic` no mesmo pedido — a nota está no próprio handler
    (`ipc_handlers.py:5669`, QUATRO-MICROFONES-01): *"o 'Aplicar' tem de VALER
    agora"*. Sem essa parte, a escolha do usuário só valeria no próximo início do
    daemon.

    **DESLIGAR GRAVA `False` — MUDOU EM 18/09/2026, e a razão é a inversão.**
    Até aqui gravava `None`, e a regra era boa enquanto o default fosse o
    silêncio: *"nunca pedi" e "não quero" deixam a ponte no chão do mesmo
    jeito*. Com a  — a ausência passou a LIGAR, e aí `None` deixou de ser
    um jeito de desligar: seria o botão que não desliga.

    O medo que a regra velha protegia continua real e agora tem outro nome: um
    `false` no disco é o **único** registro de que o usuário disse não, e é o que
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
    esquema (`profiles/schema.py:1402`), que canoniza `aa:bb:…` em `aabbcc…`; a
    do `maquina.json` é `app.actions.external_controllers.chave_de_maquina`, que
    faz o mesmo e ainda RECUSA o MAC forjado que começa em `02` — o que o
    `usb_probe_degrade` inventa somando VID, PID e bus, e que dois clones do
    mesmo modelo compartilham. Persistir esse seria gravar a FUSÃO de dois
    aparelhos num perfil.

    E ELAS PODEM DIVERGIR, medido: `chave_de_maquina` usa o `identity` quando o
    daemon o carimbou (controles EXTERNOS, `external_key`), e o mapa que chega
    ao backend é chaveado pelo `uniq` (`set_rumble_scales`). Gravar sob a chave
    do `identity` produziria um override que o motor nunca casa — a escolha
    do usuário sumiria calada, que é o defeito mais caro desta casa. Quando as duas
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
    `cfg.rumble is None` (`profiles/manager.py:2287`) e `"policy" not in
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
    1,0 (`profiles/manager.py:2220-2270`) — guardar o override só deixaria no
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
    `core/rumble.py:48` compara a política GLOBAL com o teto do ORÇAMENTO —
    nenhum dos dois é por controle —, e o caminho por controle passa um andar
    ABAIXO dele, em `core/backend_pydualsense._escalar_rumble:3797-3818`.

    "SEM TETO" CONTINUA RECUSANDO, e a recusa é a entrega: das três opções, é a
    única sem tradução honesta. `politica_do_rotulo` levanta com a razão medida,
    e este gesto não grava nada — a frase que falta é do usuário.

    É DO PERFIL, NÃO DA MÁQUINA. Sem perfil ativo não há onde guardar a força
    de um controle (`profiles/schema.py:522`), e a recusa diz em que aba
    escolher um.

    FATO ERRADO, SUBSTITUÍDO no mesmo dia: esta linha dizia *"medido no daemon
    vivo dela em 01/09/2026: `active_profile = None`, logo é ESTA a resposta que
    a tela do usuário dá hoje"*. O daemon vivo responde `active_profile =
    'meu_perfil'`. Na bancada o gesto **não recusa: grava** — no perfil que ela
    está usando — e a `gravar_e_reaplicar` ainda dispara `profile.switch`, que
    reaplica o perfil inteiro. Quem lesse a linha velha concluiria que a feature
    está inerte quando ela é o oposto, e deixaria de conferir o que o motor
    recebe.
    """
    from hefesto_dualsense4unix.interface import conexoes as _tela

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("teto-da-vibracao: o clique não disse em qual controle")
    chave = _chave_no_perfil(ctx, uniq)
    if not chave:
        raise RuntimeError(
            "Este controle não tem endereço fixo, e sem ele a força só dele "
            "não tem onde ser guardada — a escolha cairia noutro aparelho.")

    escolha = str(o.get("valor") or o.get("rotulo") or "").strip()
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


# `entrada_a_entrada.dar_nome_ao_adaptador`, e é o mesmo da janela estável

GESTO_DO_APELIDO = "adaptador-renomear"


@gesto("08-conexoes.html", "vizinho-o-que-e", grava="machine_declare")
def vizinho_o_que_e(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"— O que é? —": ela responde o que é aquele rádio vizinho."""
    chave = str(o.get("alvo") or "")
    vizinhos = {v["id"] for v in _CENA_NA_TELA.get("vizinhos", ())}
    if chave not in vizinhos:
        raise ValueError(f"vizinho-o-que-e: {chave!r} não é um rádio que está na tela")
    rotulo = str(o.get("valor") or "").strip()
    if not rotulo:
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


@gesto("08-conexoes.html", "receptor-descobrir")
def receptor_descobrir(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Descobrir» a faixa de um receptor 2.4G: o único clique é o que COMEÇA.

    O passo da vez mora em :data:`_DESCOBERTA` e quem o anda é o censo no tique
    (:func:`_andar_a_descoberta`): o receptor some da porta → mede os adaptadores sem ele; volta
    → mede com ele, e a diferença dos canais que os adaptadores evitam é a banda dele. Ninguém
    pede «já tirei» a quem acabou de tirar o próprio teclado e mouse. Nada é escrito no aparelho
    nem no rádio.
    """
    chave = str(o.get("alvo") or "")
    receptores = {str(v["id"]) for v in _CENA_NA_TELA.get("vizinhos", ()) if v.get("receptor")}
    if chave not in receptores:
        raise ValueError(f"receptor-descobrir: {chave!r} não é um receptor que está na tela")
    if _DESCOBERTA.chave == chave and _DESCOBERTA.ativa:
        return
    _DESCOBERTA.iniciar(chave, time.monotonic())


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

    E ELE RELÊ OS CONTROLES — 26/09/2026, `D-2609-O-ATUALIZAR-ENTRA-NO-EXAMINAR`
    (*«não existe diferença entre o examinar entradas e atualizar»*): o
    «Atualizar» saiu, e este clique faz também o que ele fazia — os nomes dos
    donos no BlueZ e o rascunho do mapa das portas; a declaração (o microfone e
    o perfil de cada controle) o exame já relê.
    """
    global _LOGICA
    _esquecer("bluez")
    _LOGICA = None
    _correr_o_exame_completo()


def _correr_o_exame_completo() -> None:
    """As CINCO conferências mais as ordens de serviço, sobre a máquina do usuário."""
    global _EXTRAS
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import exame_da_mesa

    declaracao = _reler_a_declaracao()
    _dispensadas_do_disco(declaracao)
    _mesa_do_radio(recarregar=True)
    _dongles(recarregar=True)
    _entradas(recarregar=True)
    _gabinete(recarregar=True)

    mesa = _mesa_declarada(declaracao)
    itens = exame_da_mesa.exame(
        # linha `vizinhanca_das_portas` do próprio Check-up. É o que fecha o
        altura_da_antena=mesa.get("altura_da_antena"),
        linha_de_visada=mesa.get("linha_de_visada"),
        # `exame_da_mesa.exame` explica que o catálogo varre o barramento
        leitura_das_ordens=_leitura_das_ordens_da_maquina(declaracao),
    )
    if not itens:
        raise RuntimeError("não consegui examinar as entradas agora")
    with contextlib.suppress(Exception):
        leitura = _conferencia_da_leitura(_ULTIMO_ESTADO)
        if leitura is not None:
            itens = [*itens, leitura]
    _EXTRAS = tuple(itens)


CHAVE_DA_LEITURA = "leitura_dos_controles"
ROTULO_DA_LEITURA = "Leitura dos controles"


def _nos_dos_controles() -> dict[str, str]:
    """``{endereço: /dev/input/eventN}`` de cada DualSense físico, pelo dono da descoberta."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.core.evdev_reader import discover_dualsense_evdevs

    return {str(chave): str(no) for chave, no in discover_dualsense_evdevs().items()}


def _abridor(porta: str) -> Callable[..., int]:
    """Por onde o exame abre o nó do controle: a porta do broker, se ela"""
    import os

    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    def abrir(caminho: str, flags: int = os.O_RDONLY) -> int:
        if porta == broker.PORTA_BROKER:
            cliente = broker.HidrawBrokerClient()
            try:
                fd = cliente.open_fd(caminho)
            finally:
                with contextlib.suppress(Exception):
                    cliente.close()
            if fd is not None:
                return fd
        return os.open(caminho, flags)

    return abrir


def _o_porque_e_a_cura_do_dono() -> tuple[str, str]:
    """``(o porquê, o que fazer)`` do aviso de grab, as duas metades da frase do dono."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.home_actions import AVISO_DE_GRAB_PORQUE

    antes, _sep, cura = AVISO_DE_GRAB_PORQUE.rpartition("; ")
    if not antes or not cura:
        return AVISO_DE_GRAB_PORQUE, ""
    return f"{antes}.", cura[:1].upper() + cura[1:]


def _o_aviso_do_grab(
    state: dict[str, Any] | None,
) -> tuple[tuple[str, str], dict[str, Any]] | None:
    """``((linha, porquê), o principal)`` quando o aviso do dono acende; ``None`` quando não."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions import home_actions

    st = state if isinstance(state, dict) else {}
    emulacao = st.get("gamepad_emulation")
    gamepad_on = bool(emulacao.get("enabled")) if isinstance(emulacao, dict) else False
    primario = next((c for c in st.get("controllers") or ()
                     if isinstance(c, dict) and c.get("connected") is True
                     and c.get("is_primary")), None)
    aviso = home_actions.aviso_de_grab(st.get("primary_grab_state"),
                                       is_primary=primario is not None,
                                       gamepad_on=gamepad_on)
    if aviso is None or primario is None:
        return None
    return aviso, primario


def _conferencia_da_leitura(state: dict[str, Any] | None, *,
                            porta: Callable[[], tuple[str, str]] | None = None,
                            grab: Callable[..., str] | None = None,
                            nos: Callable[[], dict[str, str]] | None = None) -> Any:
    """A linha do Check-up do controle que o Hefesto NÃO segura só para ele.

    O RESULTADO É DO DAEMON, E A CONDIÇÃO É DO DONO: o grab do controle
    principal (``primary_grab_state``) e a regra de quando ele vira aviso
    (`home_actions.aviso_de_grab`: o principal conectado, com o controle do
    Hefesto de pé, e o grab que FALHOU). A frase da linha e a do `?` também são
    de lá (:func:`_o_porque_e_a_cura_do_dono`). Sem aviso, não há linha — o
    aviso do dono só acende no defeito.

    A CAUSA É DO EXAME, e é o que faltava (28/09/2026): o exame pergunta à
    porta do broker (`porta_provavel`) e ao próprio nó (`estado_do_grab`), e
    escreve no diário da janela as duas linhas de cabeçalho da casa
    (`linha_da_porta`, `linha_do_grab`) com a leitura que um zero valeria ali
    (`leitura_de_zero`) — «PEGO por outro processo» é diferente de «não posso
    ler». Só pergunta ao nó quando o daemon JÁ disse que não conseguiu o grab:
    então outro processo o segura, e a tentativa não tira nada de ninguém.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item

    acende = _o_aviso_do_grab(state)
    if acende is None:
        return None
    (linha, _porque), primario = acende
    qual, motivo = (porta or broker.porta_provavel)()
    print(f"[relato] {PAGINA} · examinar-portas: {broker.linha_da_porta(qual, motivo)}",
          file=sys.stderr)
    por_endereco = {_mac(chave): str(no) for chave, no in (nos or _nos_dos_controles)().items()}
    caminho = por_endereco.get(_mac(primario.get("uniq")))
    if caminho:
        estado = (grab or broker.estado_do_grab)(caminho, abrir=_abridor(qual))
        print(f"[relato] {PAGINA} · examinar-portas: {broker.linha_do_grab(caminho, estado)}"
              f" — um zero ali seria {broker.leitura_de_zero(estado)}", file=sys.stderr)
    else:
        print(f"[relato] {PAGINA} · examinar-portas: "
              f"{broker.linha_do_grab('o nó do controle principal', broker.GRAB_SEM_NO)}",
              file=sys.stderr)
    return Item(chave=CHAVE_DA_LEITURA, rotulo=ROTULO_DA_LEITURA,
                estado="atencao",  # (noqa-acento): chave de máquina do exame
                porque=f"{linha}.", cura=_o_porque_e_a_cura_do_dono()[1] or None)


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
    meio segundo depois do clique do usuário.

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
    # :func:`_ordem_calada`.
    desfazendo = _ordem_calada(ordem)
    quando = "" if desfazendo else date.today().isoformat()
    guardar = "" if desfazendo else arranjo
    _declarar(p, {"ordens_dispensadas": {
        chave: {"quando": quando, "arranjo": guardar}}})
    _DISPENSADAS[chave] = guardar
    _reler_a_declaracao()


# deduzido: as chaves de topo do `state_full` do daemon vivo são 47, e nenhuma
# delas é `mapa` nem `maquina`. O caminho é `machine_declare` →
# `_handle_machine_declare` (`daemon/ipc_handlers.py:5669`) → `maquina.json`, e


def _gravar_o_mapa(p: Any) -> None:
    """Manda ao daemon o rascunho inteiro do mapa, e RECUSA DIZENDO se não deu."""
    ok, motivo = _resposta(p.machine_declare({"mapa": _logica_do_mapa().como_documento()}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o desenho do gabinete")


@gesto("08-conexoes.html", "escolher-aparelho")
def escolher_aparelho(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Primeiro tempo: o aparelho vai para a mão do usuário. Clicar de novo desescolhe.

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
    """Segundo tempo: põe nesta entrada o aparelho que está na mão."""
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
            f"não consegui pôr o aparelho {_a_entrada_na_frase(numero, em=True)} — "
            "ela não está no desenho do gabinete.")
    _gravar_o_mapa(p)


@gesto("08-conexoes.html", "tirar-daqui", grava="machine_declare")
def tirar_daqui(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Esvazia a entrada. Ela CONTINUA no desenho — só fica sem aparelho."""
    numero = str(o.get("entrada") or "").strip()
    if not numero:
        raise ValueError("o clique não disse de qual entrada tirar.")
    if not _logica_do_mapa().tirar(numero):
        raise RuntimeError(f"{_a_entrada_na_frase(numero, maiuscula=True)} já está vazia.")
    _gravar_o_mapa(p)


@gesto("08-conexoes.html", "nova-entrada", grava="machine_declare")
def nova_entrada(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Acrescenta a esta face o menor número que ainda não existe em face nenhuma."""
    face = str(o.get("face") or "").strip()
    if not face.isdigit():
        raise ValueError("o clique não disse em qual face acrescentar.")
    if not _logica_do_mapa().acrescentar_entrada(int(face)):
        raise RuntimeError("não achei essa face no desenho do gabinete.")
    _gravar_o_mapa(p)


@gesto("08-conexoes.html", "nova-extensao", grava="machine_declare")
def nova_extensao(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Cria a entrada-filha desta: a `10` vira `10a`, depois `10b`. Não há neta."""
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
    """Cria uma face com o nome que o usuário escreveu. Sem nome, não cria."""
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

    A RECUSA DO CABO É DO DESENHO, não do gerador: o `title` do botão apagado
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
    comecar_a_espera(uniq)


#
import threading  # noqa: E402
from collections.abc import Callable  # noqa: E402

from hefesto_dualsense4unix.integrations import (  # noqa: E402
    central_do_radio as _central_do_radio,
)
from hefesto_dualsense4unix.integrations import (  # noqa: E402
    faixa_do_wifi,
    faixas_do_ar,
    queda_do_wifi,
    receptor_sem_fio,
)
from hefesto_dualsense4unix.integrations.ar_do_adaptador import (  # noqa: E402
    CANAIS_DO_BT,
    NIVEL_ENGASGA,
    NIVEL_LISO,
    NIVEL_MEDIO,
    nivel_dos_canais,
)
from hefesto_dualsense4unix.integrations.censo_do_barramento import (  # noqa: E402
    ESPECIE_DESCONHECIDA,
)
from hefesto_dualsense4unix.integrations.radio_da_mesa import (  # noqa: E402
    CAUSA_ADAPTADOR_CHEIO,
    CAUSA_INTERFERENCIA,
    CAUSA_LONGE,
    CAUSA_SEM_SINAL,
    FATIAS_DA_PONTE,
    HZ_AUDIO_COM_MIC,
    HZ_DA_PONTE,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    N_MAX_PONTES,
    SEGURA_O_NIVEL_S,
    Diagnostico,
    atualizar_a_referencia,
    diagnosticar_o_movimento,
    nivel_do_movimento,
)

PONTES_POR_ADAPTADOR = N_MAX_PONTES
MARGINAL_DA_PONTE = (FATIAS_DA_PONTE - 1) * HZ_DA_PONTE
DICA_DO_MOVIMENTO = {
    NIVEL_LISO: "Movimento por segundo: chega tudo o que o jogo usa",
    NIVEL_MEDIO: "Movimento por segundo: chega menos que pelo USB",
    NIVEL_ENGASGA: "Movimento por segundo: engasga",
    "": "Movimento por segundo",
}
FRASE_DA_CAUSA = {
    CAUSA_LONGE: "Movimento por segundo: longe do adaptador",
    CAUSA_INTERFERENCIA: "Movimento por segundo: interferência no adaptador",
    CAUSA_ADAPTADOR_CHEIO: "Movimento por segundo: adaptador cheio",
    CAUSA_SEM_SINAL: "Movimento por segundo: sinal desconhecido",
}


def dica_do_movimento(nivel: str, causa: str = "") -> str:
    """A frase do nível; com a causa, a frase da causa (os dois números juntos)."""
    return FRASE_DA_CAUSA.get(causa) or DICA_DO_MOVIMENTO[nivel]


PISO_DOS_CANAIS = ". Usa o mínimo que o rádio aceita"
_LARGURA_DA_ENTRADA = round(2 * HZ_INPUT_SEM_MIC, 1)
_LARGURA_DO_MIC = round(2 * (HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC - HZ_INPUT_SEM_MIC), 1)
_LARGURA_DA_PONTE = round((FATIAS_DA_PONTE + 1) * HZ_DA_PONTE, 1)

#: grande, verborrágico e confuso"*.  (noqa-acento: citação literal)
SEGURE = "Segure PS + Create"
NOMEAR = "Nomear"
#: o nome do adaptador na faixa quando ele não tem nome nem entrada lida.
ADAPTADOR_SEM_NOME = "Adaptador"
ONDE_FICA = "Onde fica?"
MARCA_VARRENDO = ("Outro programa está procurando aparelhos por aqui. "
                  "Controle novo vai para outro adaptador.")
USB3_AO_LADO = "Entrada USB 3.0: faz ruído no rádio. Prefira uma 2.0."
SEM_RADIO = "Sem rádio"
ESPERANDO_O_CONTROLE = "Esperando o controle chegar."
PROCURAR_LIGADO = "LIGADO"
PROCURAR_DESLIGADO = "DESLIGADO"
TRAVESSAO_DO_PROCURAR = "—"
PROCURAR_RECUSA = "o rádio não ligou nem desligou a busca agora"
TRACO_CURTO = "\u2013"

NAO_CONECTOU = "Não conectou"
PAREAR = "Parear"
TIRAR_A_LINHA = "Tirar esta linha"
DESLIGUE_O_PROCURAR = "desligue o Procurar para esquecer"
ESQUECER_FAZ = "Tira o pareamento com este adaptador. Para voltar, use Conectar."
DESLIGADO = "Desligado"
USB = "USB"
ESQUECER = "Esquecer"
MENU_DA_LINHA = "\u22ee"
#: os dois o «Tentar de Novo» aparecia aceso e tremia.
ESPERA_NA_TELA_S = _central_do_radio.PRAZO_DO_PENDENTE_S
LEMBRA_O_NAO_CONECTOU_S = _central_do_radio.LEMBRA_O_NAO_CONECTOU_S
VOLTAS_DO_VIGIA_NA_TELA = 3

#: O glifo de cada tipo, numa tabela só: a antena (`radio`) é do adaptador e de
#: mais ninguém, e o tipo sem desenho (`outro`, `nao_sei`, o que ninguém nomeou) é o «?».
GLIFO_DO_TIPO = {
    "teclado": "teclado", "mouse": "mouse", "caixa": "caixa", "caixa_de_som": "caixa",
    "fone": "fone", "webcam": "webcam", "wifi": "wifi", "celular": "celular",
    "relogio": "relogio",
}


def glifo_do_tipo(tipo: object) -> str:
    return GLIFO_DO_TIPO.get(str(tipo or ""), "ajuda")


TIPO_PELO_ICONE = {
    "input-keyboard": "teclado", "input-mouse": "mouse", "input-tablet": "mouse",
    "audio-headset": "fone", "audio-headphones": "fone", "audio-card": "caixa",
    "camera-video": "webcam", "camera-photo": "webcam", "phone": "celular",
}
PALAVRA_DO_TIPO = {"teclado": "teclado", "mouse": "mouse", "fone": "fone",
                   "caixa": "caixa de som", "webcam": "webcam", "outro": "aparelho",
                   "celular": "celular", "relogio": "relógio"}
#: ``054C``): o DualSense e o Edge seguram PS + Create; o DualShock 4, PS +
BOTOES_DE_PAREAR = {"0ce6": "PS + Create", "0df2": "PS + Create",
                    "05c4": "PS + Share", "09cc": "PS + Share"}
ICONE_DO_CUSTO = {"mic": "mic", "som": "som", "haptica": "vibra"}
NOME_DO_CUSTO = {"mic": "microfone", "som": "som", "haptica": "vibração"}
COR_DO_TIPO = {
    "teclado": "#8b8fa8", "mouse": "#6d7186", "webcam": "#a8a08c",
    "caixa": "#8c8299", "fone": "#7e9aa8", "outro": "#606062",
    "celular": "#a89a96", "relogio": "#8a9aa8",
}
ARTIGO_DO_TIPO = {"caixa": "a", "webcam": "a"}
PASSAGEIROS = (("giro", "Giroscópio e acelerômetro"), ("touch", "Touchpad"),
               ("botoes", "Botões, sticks e gatilhos"))

FRASE_DO_DIARIO = {
    "adaptador cheio": "Pediram som com o adaptador cheio",
    "fila parada": "O adaptador parou de enviar",
    "ponte subiu": "Som além do limite",
}
PAROU_DE_REINICIAR = "parou de reiniciar o adaptador"


def _x(texto: object) -> str:
    return html.escape("" if texto is None else str(texto), quote=True)


def _ic(nome: str, classe: str = "") -> str:
    extra = f" {classe}" if classe else ""
    return f'<svg class="i{extra}" aria-hidden="true"><use href="#rd-{nome}"/></svg>'


#: o tooltip do ponto que pulsa (desenho aprovado de 05/10/2026)
PEDINDO_PARA_PAREAR = "Pedindo para parear"
#: o nome do controle que pede para parear quando ele só anuncia o nome de fábrica
CONTROLE_SEM_NOME = "Controle"


def icone_da_dica(nome: str) -> str:
    """O símbolo de um cartão: o do sprite, ou o ponto verde que pulsa do controle que pede."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.dicas_da_conexao import ICONE_PULSO

    if nome == ICONE_PULSO:
        return '<span class="cd-pulso" aria-hidden="true"></span>'
    return _ic(nome)


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


def nome_dado(nome: str) -> str:
    """O nome que ela deu (controle ou adaptador), com a primeira letra maiúscula.

    Ordem de 05/10/2026, 13h. Só a primeira letra; o resto
    fica como o usuário escreveu. Vale ao gravar e ao ler o que já estava gravado em minúscula.
    <!-- noqa-acento: citação literal -->
    """
    nome = str(nome or "").strip()
    return _maiuscula(nome)


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


SEPARADOR_DO_NOME = " \u25cf "


def nome_na_conexoes(ap: dict[str, Any]) -> str:
    """«Vitória ● Cosmic Red ● P1» — o formato do nome, SÓ na aba Conexões."""
    nome = str(ap.get("nome") or "") or str(ap.get("rotulo") or "")
    if ap.get("tipo") != "controle":
        return nome
    partes = [nome, str(ap.get("cor_nome") or "")]
    jogador = ap.get("jogador")
    if isinstance(jogador, int) and not isinstance(jogador, bool):
        partes.append(f"P{jogador}")
    return SEPARADOR_DO_NOME.join(p for p in partes if p)


def como_se_chama(ap: dict[str, Any]) -> str:
    """«<b>Vitória ● Cosmic Red ● P1</b>» — o controle pelo nome da aba Conexões."""
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
            f'<use href="#rd-{glifo_do_tipo(ap.get("tipo"))}"/></svg>')


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


def _no_ar(ap: dict[str, Any]) -> bool:
    """A linha é de quem está no ar (ou chegando) — e não o «Não Conectou» nem o"""
    return not ap.get("nao_conectou") and not ap.get("desligado")


def _pontes(cena: dict[str, Any], lid: str) -> list[dict[str, Any]]:
    """As pontes deste adaptador NA ORDEM DAS VAGAS — a «N de 2» de cada linha."""
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


def _nivel_da_linha(ap: dict[str, Any], cena: dict[str, Any], com_hz: bool) -> str:
    """O nível do movimento desta linha: o do Hz no desenho (que não tem tique),"""
    if com_hz:
        return nivel_do_movimento(ap.get("hz_mov"))
    return str((cena.get("niveis") or {}).get(str(ap.get("id")), ""))


def _dica_do_movimento_da_linha(ap: dict[str, Any], cena: dict[str, Any], nivel: str) -> str:
    return (cena.get("dicas") or {}).get(str(ap.get("id"))) or DICA_DO_MOVIMENTO[nivel]


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
    nivel = _nivel_da_linha(ap, cena, com_hz)
    dica = _dica_do_movimento_da_linha(ap, cena, nivel)
    no_nivel = f' data-nivel="{nivel}"' if nivel else ""
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
        '<span class="parte movimento" data-campo="hz-nivel" data-hef-alvo="atributo" '
        f'data-hef-atributo="data-nivel" data-alvo="{aid}"{no_nivel} '
        f'style="flex:{mov_flex} 1 0" title="Movimento por segundo">'
        '<span class="nivel" role="img" data-campo="hz-dica" data-hef-alvo="atributo" '
        f'data-hef-atributo="title" data-alvo="{aid}" title="{_x(dica)}">'
        f'{_ic("sinal")}</span><span class="hz" data-campo="hz-movimento" data-alvo="{aid}">'
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


def _tem_menu(ap: dict[str, Any]) -> bool:
    """Toda linha tem o «⋮» (desenho aprovado de 05/10/2026), menos a que espera o gesto."""
    return not ap.get("esperando") and ap.get("tipo") != "webcam"


def _pode_esquecer(ap: dict[str, Any]) -> bool:
    """O «Esquecer» do «⋮» (ESQUECER-E-LIMPAR-AS-CONEXOES-01): a linha que não conectou só
    se tira (o «Tirar esta linha» do mesmo menu)."""
    return _tem_menu(ap) and not ap.get("nao_conectou")


def _tem_x(ap: dict[str, Any]) -> bool:
    """O X fica só onde fecha um aviso: a linha «Não Conectou» (item 2 dela, a"""
    return bool(ap.get("nao_conectou")) and not ap.get("esperando")


def _o_menu(ap: dict[str, Any]) -> str:
    """O «⋮» da linha, no lugar do X: nenhum botão a mais por linha. A página"""
    if not _tem_menu(ap):
        return ""
    nome = nome_na_conexoes(ap) or str(ap.get("rotulo") or "")
    dica = f"Opções de {nome} neste adaptador"
    return (f'<button class="menu-da-linha" title="{_x(dica)}" aria-label="{_x(dica)}" '
            f'aria-haspopup="true" data-gesto="aparelho-menu" data-alvo="{_x(ap["id"])}" '
            f'data-lugar="{_x(ap.get("lugar") or "")}">'
            f'<span aria-hidden="true">{MENU_DA_LINHA}</span></button>')


def html_da_linha(ap: dict[str, Any], cena: dict[str, Any], com_hz: bool = False) -> str:
    """Uma linha da sala: desenho, nome, o que manda e recebe, qual vaga de ponte."""
    aid = _x(ap["id"])
    esperando = bool(ap.get("esperando"))
    arrasta = not ap.get("fixo") and not esperando
    nome = str(ap.get("nome") or "")
    rotulo = str(ap.get("rotulo") or "")
    quem = "controle" if ap.get("tipo") == "controle" else str(ap.get("tipo"))
    le = _x(f"{nome_na_conexoes(ap) or rotulo}, {quem}")
    if arrasta:
        abre = (f'<div class="linha" data-id="{aid}" data-alvo="{aid}" draggable="true" '
                f'tabindex="0" role="button" aria-label="{le} — Enter para mudar de adaptador">')
    else:
        estado = (" esperando" if esperando else " nao-conectou" if ap.get("nao_conectou")
                  else " desligado" if ap.get("desligado") else "")
        abre = (f'<div class="linha{estado}" data-id="{aid}" '
                f'data-alvo="{aid}" aria-label="{le}">')
    desenho = _desenho_de(ap)
    campo = (f'<input class="nome" value="{_x(nome)}" placeholder="{_x(rotulo)}" '
             'aria-label="Nome deste aparelho" title="Clique para renomear; arraste para mover" '
             f'draggable="true" data-gesto="aparelho-renomear" data-alvo="{aid}">')
    if ap.get("tipo") == "controle":
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
    vazia = '<span class="conta-da-vaga">' + TRACO_CURTO + '</span>'
    if ap.get("nao_conectou"):
        fixo = (f'<span class="quem"><span class="nome-fixo">{_x(nome_na_conexoes(ap))}'
                '</span></span>')
        abre_o_painel = ' data-abre="conectar"' if ap.get("tipo") == "controle" else ""
        refaz = bool(ap.get("pareado_aqui"))
        gesto = "parear-de-novo" if refaz else "tentar-de-novo"
        dica = ("Esquece o pareamento antigo e pareia de novo neste adaptador" if refaz
                else "Conectar de novo neste adaptador")
        return (abre + desenho + fixo + '<div class="features">'
                f'<span class="ar-selo sofrendo nao-conectou" role="img" title="{NAO_CONECTOU}" '
                f'aria-label="{NAO_CONECTOU}"></span>'
                f'<button class="btn tentar" title="{dica}" '
                f'data-gesto="{gesto}" data-alvo="{_x(ap.get("lugar") or "")}" '
                f'data-linha="{aid}"{abre_o_painel}>{PAREAR}</button></div>'
                + vazia + _o_menu(ap) + '</div>')
    if ap.get("desligado"):
        fala, dica = ((USB, "Pareado neste adaptador, ligado no USB agora") if ap.get("usb")
                      else (DESLIGADO, "Pareado neste adaptador, fora do ar"))
        return (abre + desenho + campo + '<div class="features"><span class="desligado" '
                f'title="{dica}">{fala}</span></div>'
                + vazia + _o_menu(ap) + '</div>')
    if ap.get("tipo") == "controle":
        faixa = _linha_do_controle(ap, cena, com_hz)
    elif ap.get("tipo") == "webcam":
        return (abre + desenho + campo + f'<div class="features"><span class="sem-radio" '
                f'title="Não usa rádio; só ocupa porta">{SEM_RADIO}</span></div>'
                '<span class="conta-da-vaga zero" title="Não usa rádio">'
                + TRACO_CURTO + '</span></div>')
    else:
        cor = _cor_de(ap)
        faixa = (f'<div class="faixa-do-aparelho" style="width:100%">'
                 f'<div class="vaga entrada fixa" style="flex:1 1 0;background:var(--panel);'
                 f'border-color:{_x(cor)};color:{_x(cor)}" '
                 f'title="{_x(_maiuscula(nome or rotulo))}: usa o rádio">'
                 f'{_ic(glifo_do_tipo(ap.get("tipo")))}'
                 '</div></div>')
    vaga = _vaga_de(ap, cena)
    passou = vaga > PONTES_POR_ADAPTADOR
    titulo = ("Passou do limite" if passou else f"Som {vaga} de {PONTES_POR_ADAPTADOR}"
              ) if vaga else "Sem som"
    fatias = (f'<span class="conta-da-vaga{" alem" if passou else ""}" '
              f'data-alvo="{aid}" title="{titulo}">'
              + (f"{vaga} de {PONTES_POR_ADAPTADOR}" if vaga else TRACO_CURTO) + "</span>")
    return (abre + desenho + campo + f'<div class="features">{faixa}</div>' + fatias
            + _o_menu(ap) + "</div>")


def _marcas_de_onde(lug: dict[str, Any], cena: dict[str, Any]) -> str:
    partes = []
    if lug.get("face"):
        icone = "hub" if lug.get("hub") else "placa"
        face = _x(lug["face"])
        partes.append(f'<span class="marca {"hub" if lug.get("hub") else "direto"}" role="img" '
                      f'title="{face}" aria-label="{face}">{_ic(icone)}</span>'
                      f'<span>{_x(lug.get("entrada") or "")}</span>')
    aceso = " aceso" if lug.get("varrendo") else ""
    partes.append(f'<span class="marca varrendo{aceso}" role="img" title="{MARCA_VARRENDO}" '
                  f'aria-label="{MARCA_VARRENDO}" data-campo="radio-varrendo" '
                  'data-hef-alvo="classe" data-hef-classe="aceso" data-hef-quando="sim">'
                  f'{_ic("varrendo")}</span>')
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
    partes.append(f'<span class="espera busca" data-alvo="" '
                  f'title="Segure PS + Create no controle até a luz piscar.">'
                  f'{_silhueta({})}{SEGURE}</span>')
    if not lug.get("sabido", True):
        pass
    elif not lug.get("lugar"):
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
    partes.append(_canais_do_lugar_html(lug, cena))
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
    if any(a.get("esperando") for a in moradores):
        classes.append("esperando")
    elif lug.get("nao_conectou"):
        classes.append("nao-conectou")
    if lug.get("conectando"):
        classes.append("buscando")
    if aberto:
        classes.append("aberto")
    ver = ("Esconder" if aberto else "Ver") + " os aparelhos deste adaptador"
    nome = str(lug.get("nome") or "")
    largura = max(len(nome or NOMEAR) + 2, 10)
    sino = ""
    quedas = lug.get("quedas") or []
    if quedas:
        dica = f"{len(quedas)} {'queda' if len(quedas) == 1 else 'quedas'} — ver quando"
        sino = (f'<button class="sino" title="{dica}" aria-label="{dica}" '
                f'data-gesto="adaptador-historico" data-alvo="{lid}">{_ic("aviso")}</button>')
    chegou = " ".join(sorted(_x(c) for c in lug.get("chegou") or ()))
    unica = len(cena.get("lugares") or ()) == 1
    seta = "" if unica else (
        f'<button class="abre-lugar" aria-expanded="{str(aberto).lower()}" title="{ver}" '
        f'aria-label="{ver}" data-gesto="abrir-adaptador" data-alvo="{lid}">'
        '<span aria-hidden="true">▶</span></button>')
    arrasta = "" if unica else ' draggable="true" title="Arraste para mudar a ordem"'
    topo = (
        f'<div class="lugar-topo"{arrasta}>' + seta
        + f'<input class="lugar-nome cor-{cor_do_adaptador(cena, str(lug["id"]))}" '
        f'value="{_x(nome)}" placeholder="{NOMEAR}" '
        f'aria-label="Nome deste adaptador" style="width:{largura}ch" '
        f'data-gesto="adaptador-renomear" data-alvo="{lid}">'
        + _marcas_de_onde(lug, cena) + sino + _barra_do_lugar(lug, cena)
        + _conta_do_lugar(lug, cena) + "</div>")
    linhas = "".join(html_da_linha(ap, cena, com_hz) for ap in moradores)
    ocupado = _ocupado(cena)
    apagado = (f'{" apagado" if ocupado else ""}" aria-disabled="{str(ocupado).lower()}" '
               'data-campo="radio-ocupado" data-hef-alvo="classe" data-hef-classe="apagado" '
               'data-hef-atributo="aria-disabled')
    lampada = ""
    if cena.get("proposta") and cena["proposta"].get("destino") == lug["id"]:
        lampada = (f'<button class="lampada{apagado}" title="Quem funciona melhor aqui" '
                   f'aria-label="Quem funciona melhor aqui" data-gesto="sugerir-alocacao" '
                   f'data-alvo="{lid}">{_ic("lampada")}</button>')
    # sem «Arraste outro para cá» (desenho aprovado de 05/10/2026): a linha se arrasta, e o
    # Enter nela abre «Para onde vai»
    fila = f'<div class="soltar-fila">{lampada}</div>' if lampada else ""
    corpo = f'<div class="aparelhos" data-alvo="{lid}">{linhas}{fila}</div>'

    return (f'<div class="{" ".join(classes)}" data-id="{lid}" data-alvo="{lid}" '
            f'data-chegou="{chegou}" data-campo="radio-conectando" data-hef-alvo="classe" '
            f'data-hef-classe="buscando" data-hef-quando="sim">' + topo + corpo + "</div>")


def _como_se_pareia(ap: dict[str, Any]) -> str:
    """O que ela faz com a mão, pelo tipo — o gesto do modelo, ou o genérico."""
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


def pergunta_de_esquecer(ap: dict[str, Any], lug: dict[str, Any]) -> str:
    """A pergunta ANTES do «Esquecer» (item 3): quem sai, e de onde — só deste"""
    return (f"Esquecer {como_se_chama(ap)} n{como_se_chama_o_lugar(lug)}?<br>"
            "Só o pareamento deste adaptador sai. Para voltar, use Conectar.")


def _moldes_de_esquecer(cena: dict[str, Any]) -> str:
    """O menu «⋮» de cada linha que tem pareamento ali, e a pergunta do
    «Esquecer» dele. O menu é um painel (``data-painel="menu"``, pelo par
    ``linha|adaptador``) com o «Esquecer», como o «⋮» das Configurações do
    COSMIC da foto 8 dela — sem «Desconectar» (a R7 dela: o desconectar mora
    no mover) e sem «Renomear» (é o campo do nome). O «sim» da pergunta é o
    ``confirmar-esquecer``, e o endereço é ``(linha, adaptador)`` —
    ``data-esquecer`` separa estas das perguntas de mover, que têm a mesma forma."""
    lugares = {str(lug["id"]): lug for lug in cena.get("lugares", ()) if lug.get("sabido", True)}
    moldes = []
    for ap in cena.get("aparelhos", ()):
        if not _tem_menu(ap):
            continue
        lug = lugares.get(str(ap.get("lugar")))
        if lug is None:
            continue
        alvo, lid = _x(ap["id"]), _x(lug["id"])
        titulo = _x(nome_na_conexoes(ap) or str(ap.get("rotulo") or ""))
        esquece = _pode_esquecer(ap)
        itens = ([("sair", ESQUECER, f'data-gesto="esquecer-aparelho" data-alvo="{alvo}" '
                                     f'data-lugar="{lid}"')] if esquece else [])
        if _tem_x(ap):
            itens.append(("sair", TIRAR_A_LINHA, f'data-gesto="dispensar-linha" data-alvo="{alvo}" '
                                                 f'data-lugar="{lid}"'))
        moldes.append(f'<template class="painel-molde" data-painel="menu" '
                      f'data-alvo="{alvo}|{lid}" data-titulo="{titulo}">'
                      + (f'<p class="explica">{ESQUECER_FAZ}</p>' if esquece else "")
                      + _botoes(itens) + '</template>')
        if not esquece:
            continue
        moldes.append(f'<template class="pergunta-molde" data-esquecer="1" '
                      f'data-alvo="{alvo}" data-destino="{lid}" '
                      f'data-sim="{ESQUECER}" data-gesto="confirmar-esquecer">'
                      f'{pergunta_de_esquecer(ap, lug)}</template>')
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
        vem = [(("ds" if a.get("tipo") == "controle"
                 else glifo_do_tipo(a.get("tipo"))),
                nome_na_conexoes(a),
                f'data-aparelho="{_x(a["id"])}" data-destino="{_x(lid)}"')
               for a in movidos if a.get("lugar") != lid]
        titulo = ("Quem vem para " + (lug.get("nome") or ("a " + str(lug.get("entrada") or "")))
                  + "?") if vem else "Nada para trazer"
        moldes.append(f'<template class="painel-molde" data-painel="quem-vem" '
                      f'data-alvo="{_x(lid)}" data-titulo="{_x(titulo)}">'
                      f'{_botoes(vem) if vem else ""}</template>')
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
    _, rotulos = _tipos_de_radio()
    for viz in _vizinhos_sem_rede(cena):
        itens = [(glifo_do_tipo(tipo), rotulo,
                  f'data-gesto="vizinho-o-que-e" data-alvo="{_x(viz["id"])}" '
                  f'value="{_x(rotulo)}"')
                 for tipo, rotulo in rotulos.items()]
        moldes.append(f'<template class="painel-molde" data-painel="o-que-e" '
                      f'data-alvo="{_x(viz["id"])}" data-titulo="O que é este rádio?">'
                      f'{_botoes(itens)}</template>')
    busca = _onde_espera(lugares, list(cena.get("aparelhos") or ()))
    destino = busca or cena.get("destino_do_conectar") or (lugares[0]["id"] if lugares else "")
    agora_nao = bool(busca) and str(cena.get("passo_da_espera") or "") not in (
        _central_do_radio.PASSOS_EM_QUE_O_DESTINO_MUDA)

    def chip(lug: dict[str, Any]) -> str:
        lid = str(lug["id"])
        aceso = str(lid == destino).lower()
        if agora_nao and lid != busca:
            return (f'<button class="op" aria-pressed="{aceso}" aria-disabled="true" '
                    f'title="{ESPERANDO_O_CONTROLE}" data-alvo="{_x(lid)}">'
                    f'{_x(_titulo_do_lugar(lug))}</button>')
        return (f'<button class="op" aria-pressed="{aceso}" '
                f'title="Com som: {len(_pontes(cena, lid))} de {PONTES_POR_ADAPTADOR}" '
                f'data-gesto="escolher-adaptador" data-alvo="{_x(lid)}">'
                f'{_x(_titulo_do_lugar(lug))}</button>')

    chips = "".join(chip(lug) for lug in lugares)
    achados = "".join(
        f'<div class="achado" data-alvo="{_x(a["id"])}">'
        + (_ic("ds", "ds cheio") if a.get("tipo") == "controle"
           else _ic(glifo_do_tipo(a.get("tipo")), "ico"))
        + f'<span class="nome">{_x(a.get("nome"))}</span>'
        + (f'<span class="forca" title="Sinal: mais perto de zero, mais perto">'
           f'{_x(a["forca"])} dBm</span>' if a.get("forca") is not None else "")
        + (f'<button class="btn" data-gesto="conectar-aparelho" data-alvo="{_x(a["id"])}">'
           'Conectar</button>' if a.get("conhecido") else
           f'<button class="btn" data-gesto="parear-aparelho" data-alvo="{_x(a["id"])}">'
           'Parear</button>')
        + "</div>" for a in cena.get("perto", ()) if a.get("adaptador") == destino)
    procurando = any(lug.get("conectando") for lug in lugares)
    titulo = (' data-titulo="Procurando" data-pulso="1"' if procurando
              else ' data-titulo="Conectar"')
    moldes.append(f'<template class="painel-molde" data-painel="conectar" data-alvo=""'
                  f'{titulo}>'
                  f'<div class="conectar"><div class="escolha-lugar" role="group" '
                  f'aria-label="Em qual adaptador conectar">{chips}</div>'
                  f'<div class="achados">{achados}</div></div></template>')
    return "".join(moldes)


NENHUM_ADAPTADOR = "Nenhum adaptador Bluetooth encontrado."


def html_da_sala(cena: dict[str, Any], com_hz: bool = False) -> str:
    """Os cartões dos adaptadores, e só eles."""
    if not cena.get("lugares"):
        if not cena.get("lido", True):
            return str(_monta().NADA_A_DIZER)
        return f'<div class="sala-vazia">{NENHUM_ADAPTADOR}</div>'
    return "".join(html_do_lugar(lug, cena, com_hz) for lug in cena["lugares"])


def html_dos_moldes(cena: dict[str, Any]) -> str:
    """As perguntas, os painéis e o balão prontos, em `<template>` — a página os abre."""
    if not cena.get("lugares"):
        return ""
    perguntas = "" if _ocupado(cena) else _moldes_de_pergunta(cena)
    return perguntas + _moldes_de_esquecer(cena) + _moldes_de_painel(cena) + _molde_do_balao(cena)


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


CORES_DOS_ADAPTADORES = ("cyan", "purple", "pink", "yellow")
COR_DO_QUINTO_EM_DIANTE = "comment"
NOME_DO_WIFI = "Wi-Fi"


def cor_do_adaptador(cena: dict[str, Any], lid: str) -> str:
    """O token de cor da POSIÇÃO do adaptador na ordem de produto: caixa, pista e porta leem
    daqui."""
    ids = [str(lug["id"]) for lug in cena.get("lugares") or ()]
    posicao = ids.index(str(lid)) if str(lid) in ids else len(ids)
    return (CORES_DOS_ADAPTADORES[posicao] if posicao < len(CORES_DOS_ADAPTADORES)
            else COR_DO_QUINTO_EM_DIANTE)


def nome_do_grupo(viz: dict[str, Any]) -> tuple[str, str, str]:
    """`(nome, procedência, glifo)` de um rádio vizinho — a ordem da mais forte à mais fraca.

    A palavra de produto vence; a do kernel IDÊNTICA à da lista sai sem interrogação (a
    procedência `lido` põe o selo à vista); a equivalência (Câmera → Webcam) fica
    com a interrogação; depois o nome que o aparelho dá de si; por fim a palavra do censo.
    Nada disto grava: o `maquina.json` só recebe o gesto do usuário.
    """
    tipo = str(viz.get("tipo") or "")
    sugestao = str(viz.get("sugestao") or "")
    if tipo:
        return (str(viz.get("nome") or _maiuscula(tipo.replace("_", " "))), "dela",
                glifo_do_tipo(tipo))
    glifo = glifo_do_tipo(viz.get("sugestao_tipo"))
    if sugestao and sugestao == str(viz.get("lido") or ""):
        return _maiuscula(sugestao), "lido", glifo
    if sugestao:
        return f"{_maiuscula(sugestao)}?", "equivale", glifo
    if viz.get("produto"):
        return str(viz["produto"]), "produto", "ajuda"
    return ESPECIE_DESCONHECIDA, "ninguem", "ajuda"


def _faixa_da_rede(rede: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """`(faixa, largura informada)` da rede, pela conta do padrão."""
    conta = faixa_do_wifi.faixa_no_bluetooth(faixa_do_wifi.RedeSemFio(
        no=str(rede.get("no") or ""), frequencia_mhz=int(rede["mhz"]),
        largura_mhz=rede.get("largura")))
    return {"ini": conta.ini, "fim": conta.fim, "como": conta.como}, conta.largura_informada


def _canais_do_lugar_html(lug: dict[str, Any], cena: dict[str, Any]) -> str:
    """O «N/79» do adaptador, na caixa dele."""
    canais = _canais_de(cena, str(lug["id"]))
    if canais is None:
        return ""
    nivel = nivel_dos_canais(canais)
    dica = (f"Usa os {CANAIS_DO_BT} canais" if canais == CANAIS_DO_BT else
            f"Evita {CANAIS_DO_BT - canais} dos {CANAIS_DO_BT} canais (vizinhos)")
    dica += PISO_DOS_CANAIS if nivel == NIVEL_ENGASGA else ""
    return (f'<span class="canais-do-lugar" data-nivel="{nivel}" '
            f'role="img" title="{dica}" aria-label="{dica}">'
            f'{_ic("radio")}{canais}/{CANAIS_DO_BT}</span>')


#: O tipo que tem cor própria na régua (a folha da seção define ``--c-<tipo>``); o resto cai
#: em ``outro``. O controle leva o plástico dele, lido do aparelho.
TIPOS_COM_COR_NA_REGUA = frozenset({
    "celular", "relogio", "fone", "caixa", "teclado", "mouse", "wifi", "ruido"})
#: A legenda do título: quem é o tipo e como ele se chama na tela.
LEGENDA_DAS_FAIXAS = (
    ("controle", "Controles"), ("celular", "Celular"), ("relogio", "Relógio"),
    ("wifi", "Wi-Fi"), ("teclado", "Teclado"), ("mouse", "Mouse"), ("ruido", "Ruído"))


def _evitados_do_lugar(cena: dict[str, Any], lid: str) -> frozenset[int] | None:
    """Os canais que o adaptador evita; ``None`` = não se mede (e zero evitado é um fato)."""
    faixas = [v for v in cena.get("evitados", ()) if v.get("lugar") == lid]
    if not faixas and not cena.get("canais_medidos", {}).get(lid, False):
        return None
    return frozenset(c for v in faixas for c in range(int(v["ini"]), int(v["fim"])))


def _a_faixa_do_aparelho(cena: dict[str, Any], lid: str, ap: dict[str, Any]) -> Any:
    """O aparelho como a régua o lê: o enlace dele (mapa, a qualidade, LE) pelo endereço."""
    lido = _dicionario(_dicionario(cena.get("enlaces")).get(lid)).get(_so_hex(str(ap["id"])))
    lido = _dicionario(lido)
    evitados = lido.get("canais_evitados")
    tipo = str(ap.get("tipo") or "outro")
    nome = (nome_na_conexoes(ap) if tipo == "controle" else str(ap.get("nome") or "")
            ) or PALAVRA_DO_TIPO.get(tipo, "aparelho").capitalize()
    return faixas_do_ar.AparelhoNoAdaptador(
        id=str(ap["id"]), tipo=tipo, nome=nome,
        cor=str(ap.get("cor") or "") if tipo == "controle" else "",
        evitados=frozenset(evitados) if isinstance(evitados, list) else None,
        le=bool(lido.get("le")), qualidade_do_enlace=lido.get("qualidade_do_enlace"),
        rssi=lido.get("rssi")
        if lido.get("rssi") is not None else ap.get("sinal"))


def _a_regua_dos_adaptadores(cena: dict[str, Any]) -> list[Any]:
    adaptadores = []
    for lug in cena.get("lugares") or ():
        lid = str(lug["id"])
        aparelhos = tuple(_a_faixa_do_aparelho(cena, lid, a) for a in _moradores(cena, lid)
                          if a.get("tipo") != "webcam" and _no_ar(a))
        adaptadores.append(faixas_do_ar.Adaptador(
            id=lid, nome=_titulo_do_lugar(lug) or ADAPTADOR_SEM_NOME,
            cor=cor_do_adaptador(cena, lid),
            evitados=_evitados_do_lugar(cena, lid), aparelhos=aparelhos))
    return adaptadores


def _canal_do_wifi(mhz: int) -> str:
    """«2.4 GHz · canal 11»: a banda e o canal, pela frequência que a rede anuncia."""
    if mhz < 2500:
        return f"2,4 GHz · canal {14 if mhz == 2484 else (mhz - 2407) // 5}"
    if mhz < 5925:
        return f"5 GHz · canal {(mhz - 5000) // 5}"
    return f"6 GHz · canal {(mhz - 5950) // 5}"


def _usb_da_porta(cena: dict[str, Any], quem: str) -> str:
    return next((str(p.get("usb") or "") for p in cena.get("portas", ()) if p.get("ocupa") == quem),
                "")


def _vizinhos_sem_rede(cena: dict[str, Any]) -> list[dict[str, Any]]:
    """Os rádios vizinhos que NÃO são uma rede Wi-Fi lida (essa tem a linha dela, sem botão)."""
    vizinhos = list(cena.get("vizinhos") or ())
    das_redes = {str(v["id"]) for r in cena.get("wifi") or ()
                 if (v := _o_vizinho_da_rede(r, vizinhos)) is not None}
    return [v for v in vizinhos if str(v["id"]) not in das_redes]


NOTA_DO_USB_3_NO_2_4 = "USB 3.0 + 2,4 GHz"
DICA_DO_USB_3_NO_2_4 = (
    "USB 3.0 e 2,4 GHz juntos: o link USB 3.0 fica colado na antena e costuma derrubar a "
    "placa. Em 5 GHz ou numa porta USB 2.0 ela não cai.")


def _o_vizinho_da_rede(
    rede: dict[str, Any], vizinhos: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """O rádio vizinho que É esta rede: pelo `vid:pid` (que sobrevive à queda) e, sem ele,
    pelo nó USB."""
    chave = str(rede.get("chave") or "")
    if chave.startswith("usb:"):
        achado = next((v for v in vizinhos if str(v["id"]) == chave[4:]), None)
        if achado is not None:
            return achado
    no = str(rede.get("no") or "")
    return next((v for v in vizinhos if no and str(v.get("no") or "") == no), None)


def _id_da_rede(rede: dict[str, Any], viz: dict[str, Any] | None, i: int) -> str:
    """O id da linha: o do vizinho (`vid:pid`), senão o da chave; o nome da interface nunca."""
    if viz is not None:
        return str(viz["id"])
    chave = re.sub(r"[^0-9a-z]+", "-", str(rede.get("chave") or "").lower()).strip("-")
    return f"wifi-{chave}" if chave and not chave.startswith("if-") else f"wifi-{i}"


def _a_saude_do_wifi(rede: dict[str, Any], usb3: bool) -> tuple[Any, str, str]:
    """`(selo, nota, dica)` do Wi-Fi conectado: as quedas que o diário contou e a causa
    conhecida (USB 3.0 colado no 2.4 GHz)."""
    q = rede.get("quedas")
    selo = None
    if isinstance(q, dict) and int(q.get("n") or 0) > 0:
        contadas = queda_do_wifi.Quedas(n=int(q["n"]), minutos=int(q.get("min") or 1))
        selo = faixas_do_ar.Selo(queda_do_wifi.nivel(contadas), queda_do_wifi.em_palavras(contadas))
    colado = usb3 and int(rede["mhz"]) < 2500
    return selo, NOTA_DO_USB_3_NO_2_4 if colado else "", DICA_DO_USB_3_NO_2_4 if colado else ""


_DESCOBERTA = receptor_sem_fio.Descoberta()
#: de quanto em quanto a porta se relê enquanto o «Descobrir a faixa» anda (só então).
RELER_A_PORTA_NO_GESTO_S = 2.0
#: o último vizinho que o gesto viu na porta: com o receptor TIRADO a linha dele some do censo, e
#: é nela que o passo («Medindo sem ele…», «Ponha o receptor de volta») se diz.
_VISTO_NO_GESTO: dict[str, dict[str, Any]] = {}
#: quem guarda a banda achada em disco (a régua injeta o dela: nenhum teste escreve no config).
_GRAVAR_A_BANDA: Callable[[Any], Any] | None = None


def _a_descoberta() -> Any:
    return _DESCOBERTA


def _evitados_dos_adaptadores(ar: dict[str, Any]) -> dict[str, tuple[int, ...] | None]:
    """`{adaptador: canais que ele evita agora}`; `None` quando o adaptador não mede."""
    saida: dict[str, tuple[int, ...] | None] = {}
    for fim, publicado in ar.items():
        lista = publicado.get("canais_evitados") if isinstance(publicado, dict) else None
        saida[_mac(fim) or str(fim)] = (
            tuple(int(c) for c in lista) if isinstance(lista, list) else None)
    return saida


def _o_receptor_tirado(vizinhos: list[dict[str, Any]]) -> dict[str, Any] | None:
    """O vizinho do gesto em curso quando ele não está na porta agora; senão, `None`."""
    d = _DESCOBERTA
    if not d.ativa or any(v["id"] == d.chave for v in vizinhos):
        return None
    return _VISTO_NO_GESTO.get(d.chave)


def _andar_a_descoberta(ar: dict[str, Any], agora: float, presente: bool | None = None) -> None:
    """O tique do «Descobrir a faixa»: o censo anda os passos (``presente``: o receptor está na
    porta agora; ``None``: o censo não leu), fecha a medida e, achada a banda, guarda-a."""
    d = _DESCOBERTA
    if not d.ativa:
        return
    d.andar(agora, lambda: _evitados_dos_adaptadores(ar), presente)
    if d.passo == receptor_sem_fio.PASSO_ACHOU and d.banda is not None and not d.guardada:
        d.guardada = True
        _guardar_a_banda(d.chave, d.banda)


def _guardar_a_banda(chave: str, banda: tuple[int, int]) -> None:
    """A faixa medida vai ao `maquina.json`, com o dia: é o que a pinta nas próximas vezes."""
    declaracao = {"radios": {chave: {"banda": [banda[0], banda[1]],
                                     "banda_em": time.strftime("%Y-%m-%d")}}}
    perfil._com_o_src()
    gravar = _GRAVAR_A_BANDA
    if gravar is None:
        from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_mesa

        gravar = declarar_a_mesa
    gravar(declaracao)
    _reler_a_declaracao()


def _banda_declarada(declaracao: Any, chave: str) -> list[int] | None:
    """`[ini, fim)` que o «Descobrir» mediu para este `vid:pid`, ou `None`."""
    radios = getattr(getattr(declaracao, "mesa", None), "radios", None) or {}
    banda = getattr(radios.get(chave), "banda", None)
    return [int(banda[0]), int(banda[1])] if banda else None


def _passo_da_linha(chave: str) -> str:
    """O passo do «Descobrir» DESTE receptor, ou `""` quando ele não está em curso."""
    d = _DESCOBERTA
    return d.passo if d.chave == chave else ""


def _o_botao_da_descoberta(linha: Any) -> tuple[str, str]:
    """`(texto, rótulo do botão)` da linha sem faixa de um receptor; `("", "")` se não é dele."""
    if linha.sem_faixa != faixas_do_ar.NAO_DESCOBERTA:
        return "", ""
    passo = _passo_da_linha(linha.id)
    if passo in (receptor_sem_fio.PASSO_TIRE, receptor_sem_fio.PASSO_PONHA,
                 receptor_sem_fio.PASSO_MEDINDO_SEM, receptor_sem_fio.PASSO_MEDINDO_COM):
        return receptor_sem_fio.FRASE_DO_PASSO[passo], ""
    # a frase do passo que não achou é da descoberta («Não achei…»); a tela diz sem primeira pessoa
    frase = FAIXA_NAO_ENCONTRADA if passo == receptor_sem_fio.PASSO_NADA else linha.sem_faixa
    return frase, receptor_sem_fio.BOTAO_DE_COMECAR


def _os_outros_radios(cena: dict[str, Any]) -> list[tuple[Any, str]]:
    """`(ocupante, rótulo html)` do Wi-Fi conectado e de cada rádio vizinho, na ordem da tela."""
    vizinhos = list(cena.get("vizinhos") or ())
    saida: list[tuple[Any, str]] = []
    da_rede: set[str] = set()
    tirado = cena.get("descobrindo_ausente")
    for i, rede in enumerate(cena.get("wifi") or ()):
        viz = _o_vizinho_da_rede(rede, vizinhos)
        quem = _id_da_rede(rede, viz, i)
        if viz is not None:
            da_rede.add(quem)
        faixa, _informada = _faixa_da_rede(rede)
        banda = (faixas_do_ar.banda_do_intervalo(faixa["ini"], faixa["fim"])
                 if faixa["como"] == faixa_do_wifi.PROVAVEL else frozenset())
        usb3 = _usb_da_porta(cena, quem) == "3.0"
        sub = _canal_do_wifi(int(rede["mhz"]))
        selo, nota, dica = _a_saude_do_wifi(rede, usb3)
        saida.append((faixas_do_ar.Ocupante(
            id=quem, tipo="wifi", nome=NOME_DO_WIFI, sub=sub, banda=banda,
            sem_faixa=faixas_do_ar.FORA_DA_FAIXA, selo=selo, nota=nota, dica=dica),
            _rotulo_do_ocupante(NOME_DO_WIFI, "wifi", sub)))
    for viz in [*vizinhos, *([tirado] if tirado else [])]:
        if str(viz["id"]) in da_rede or _nao_e_sem_fio(viz):
            continue
        nome, procedencia, glifo = nome_do_grupo(viz)
        tipo = "wifi" if glifo == "wifi" else str(viz.get("tipo") or viz.get("sugestao_tipo")
                                                  or "outro")
        banda = viz.get("banda")
        receptor = bool(viz.get("receptor")) or tipo in ("teclado", "mouse")
        sub = ("" if tipo == "wifi" else
               ("Receptor 2,4G · descoberto" if banda else "Receptor 2,4G") if receptor else "")
        sem_faixa = (faixas_do_ar.SEM_REDE if tipo == "wifi" else
                     faixas_do_ar.NAO_DESCOBERTA if receptor
                     else faixas_do_ar.NAO_SE_MEDE)
        selo = receptor_sem_fio.selo_da_saude(viz.get("saude"), tipo) if receptor else None
        saida.append((faixas_do_ar.Ocupante(
            id=str(viz["id"]), tipo=tipo, nome=nome, sub=sub,
            banda=(frozenset(range(int(banda[0]), int(banda[1])))
                   if isinstance(banda, (list, tuple)) and len(banda) == 2 else None),
            sem_faixa=sem_faixa,
            selo=faixas_do_ar.Selo(selo[0], selo[1]) if selo else None,
            nota=selo[2] if selo else ""),
            _rotulo_do_vizinho(viz, nome, procedencia, glifo)))
    return saida


#: o que é aparelho USB e não fala pelo ar: não ganha linha entre os sem fio (05/10/2026).
NAO_SAO_SEM_FIO = frozenset({"webcam", "caixa_de_som", "caixa"})


def _nao_e_sem_fio(viz: dict[str, Any]) -> bool:
    """A webcam e a caixa de som no cabo dividem o barramento, não o ar."""
    return str(viz.get("tipo") or viz.get("sugestao_tipo") or "") in NAO_SAO_SEM_FIO


def _rotulo_do_ocupante(nome: str, tipo: str, sub: str) -> str:
    """Só o ícone; o nome (e a banda) no tooltip — desenho aprovado de 05/10/2026."""
    dica = " · ".join(t for t in (nome, sub) if t)
    return (f'<div class="ar-rot" title="{_x(dica)}" role="img" aria-label="{_x(dica)}">'
            f'{_ic(glifo_do_tipo(tipo))}</div>')


def _rotulo_do_vizinho(viz: dict[str, Any], nome: str, procedencia: str, glifo: str) -> str:
    """Só o ícone, que é o botão do «O que é?»; o nome mora no tooltip e no `aria-label`."""
    dica = _x({
        "dela": f"{nome}: canal que o sistema não diz. Toque para trocar.",
        "lido": f"{nome}, lido pelo computador. Toque para trocar.",
        "equivale": f"{nome} Toque para dizer o que é.",
        "produto": f"{nome}. Toque para dizer o que é.",
    }.get(procedencia, "Rádio sem nome. Toque para dizer o que é."))
    return (f'<div class="ar-rot"><button class="rotulo vizinho" title="{dica}" '
            f'aria-label="{_x(nome)}" data-gesto="vizinho-o-que-e" data-alvo="{_x(viz["id"])}">'
            f'{_ic(glifo)}</button></div>')


def _cor_na_regua(tipo: str, cor: str = "") -> str:
    if tipo == "controle":
        return cor or "var(--texto-suave)"
    return f"var(--c-{tipo if tipo in TIPOS_COM_COR_NA_REGUA else 'outro'})"


def _o_canal(c: Any, cores: dict[str, str], nomes: dict[str, str]) -> str:
    mhz = 2402 + c.canal
    onde = f"Canal {c.canal} · {mhz} MHz"
    if c.estado == faixas_do_ar.BOM:
        return f'<i class="b" title="{onde} · bom"></i>'
    if c.estado == faixas_do_ar.PERDIDO:
        cor = cores.get(c.dono, "var(--c-ruido)")
        dono = nomes.get(c.dono, faixas_do_ar.NOME_DO_RUIDO)
        return (f'<i class="p" title="{onde} · perdido para {_x(dono)}">'
                f'<u style="--m:{_x(cor)}"></u></i>')
    if c.estado == faixas_do_ar.OCUPADO:
        marca = (f'<u style="--m:{_x(cores.get(c.marca, "var(--c-ruido)"))}"></u>'
                 if c.marca else "")
        quem = f" · {_x(nomes.get(c.marca, ''))} perde aqui" if c.marca else ""
        return f'<i class="b" title="{onde} · ocupado aqui{quem}">{marca}</i>'
    return f'<i title="{onde} · livre para os outros"></i>'


def _o_selo(selo: Any, titulo: str = "") -> str:
    if selo is None:
        return ""
    nivel = _x(str(selo.nivel).replace(" ", "-"))
    dica = f' title="{_x(titulo)}"' if titulo else ""
    return f'<span class="ar-selo {nivel}"{dica}>{_x(selo.texto)}</span>'


#: o tooltip do ponto verde e do vazado (desenho aprovado de 05/10/2026: o verde já diz «bom»).
TUDO_CERTO = "Tudo certo"
FAIXA_NAO_DESCOBERTA = "Faixa ainda não descoberta · clique para descobrir"
FAIXA_NAO_ENCONTRADA = "Faixa não encontrada"
FAIXA_NAO_ACHADA = f"{FAIXA_NAO_ENCONTRADA} · clique para tentar de novo"


def _o_ponto(linha: Any, descobrir: str, vazado: str = FAIXA_NAO_DESCOBERTA) -> str:
    """O estado da linha num ponto: verde = bom, laranja ou vermelho = problema, vazado = sem faixa.

    O texto do problema («3 teclas presas em 1 h») vai só no tooltip; o verde diz «Tudo certo».
    Para o leitor de tela o ponto diz a palavra inteira («Boa 74/79»): a cor nunca vai sozinha.
    O vazado do receptor ainda não descoberto é o próprio gesto de descobrir.
    """
    selo = linha.selo
    ruim = selo is not None and selo.nivel != "boa"
    nivel = _x(str(selo.nivel).replace(" ", "-")) if selo is not None else ""
    junta = " " if linha.nota.startswith("em ") else " · "
    dito = (_maiuscula(junta.join(t for t in (selo.texto, linha.nota) if t)) if selo is not None
            else _maiuscula(linha.sem_faixa))
    # o que se leu do enlace continua no tooltip, depois do estado
    ja_dito = selo is not None and "tira canais" in selo.texto
    extras = [t for t in (
        f"sinal {linha.rssi} dBm" if isinstance(linha.rssi, int) else "",
        (f"qualidade do enlace {linha.qualidade_do_enlace}/255"
         if isinstance(linha.qualidade_do_enlace, int) else ""),
        f"tira canais de {linha.tira_de}" if linha.tira_de and not ja_dito else "",
        linha.dica) if t]
    dica = " · ".join([TUDO_CERTO if selo is not None and not ruim else dito, *extras])
    fala = " · ".join([dito, *extras])
    if descobrir:
        dica = "\n".join(t for t in (dica if ruim else "", vazado) if t)
        fala = " · ".join(t for t in (fala if selo is not None else "", vazado) if t)
        return (f'<button class="ar-selo {nivel} sem" type="button" '
                f'data-gesto="receptor-descobrir" data-alvo="{_x(linha.id)}" '
                f'title="{_x(dica)}" aria-label="{_x(fala)}"></button>')
    classe = nivel if selo is not None else "sem"
    return (f'<span class="ar-selo {classe}" role="img" title="{_x(dica)}" '
            f'aria-label="{_x(fala)}"></span>')


def _a_linha_do_ar(linha: Any, rot: str, cores: dict[str, str], nomes: dict[str, str]) -> str:
    cor = cores[linha.id]
    descobrir = ""
    vazado = (FAIXA_NAO_ACHADA if _passo_da_linha(linha.id) == receptor_sem_fio.PASSO_NADA
              else FAIXA_NAO_DESCOBERTA)
    if linha.celulas:
        resumo = (f"{nomes[linha.id]}: {linha.bons} dos {CANAIS_DO_BT} canais bons"
                  if linha.bons is not None else f"{nomes[linha.id]}: faixa ocupada")
        faixa = (f'<div class="ar-faixa" role="img" aria-label="{_x(resumo)}">'
                 + "".join(_o_canal(c, cores, nomes) for c in linha.celulas) + "</div>")
    else:
        frase, descobrir = _o_botao_da_descoberta(linha)
        # o passo do gesto guiado («Tire o receptor da porta») é a única frase que a faixa diz
        passo = f"<span>{_x(frase)}</span>" if frase and not descobrir else ""
        faixa = (f'<div class="ar-faixa sem" role="img" '
                 f'aria-label="{_x(frase or linha.sem_faixa)}">{passo}</div>')
    donos = " ".join(dict.fromkeys(t for t, _n in linha.quem))
    return (f'<div class="ar-linha" data-id="{_x(linha.id)}" data-tipo="{_x(linha.tipo)}" '
            f'data-briga="{_x(" ".join(linha.briga))}" data-quem="{_x(donos)}" tabindex="0" '
            f'style="--cor:{_x(cor)}">{rot}{faixa}'
            f'<div class="ar-estado">{_o_ponto(linha, descobrir, vazado)}</div></div>')


def _o_rotulo_do_aparelho(linha: Any) -> str:
    glifo = (_silhueta({"cor": linha.cor}, "ds") if linha.tipo == "controle"
             else _ic(glifo_do_tipo(linha.tipo)))
    return (f'<div class="ar-rot" title="{_x(linha.nome)}" role="img" '
            f'aria-label="{_x(linha.nome)}">{glifo}</div>')


#: uma entrada com mais aparelhos que isto põe as linhas em duas colunas.
LINHAS_NUMA_COLUNA = 3
OUTROS_SEM_FIO = "Outros dispositivos sem fio"


def _em_colunas(linhas: list[str]) -> list[str]:
    """Até três linhas, uma coluna; mais, duas colunas com metade de cada lado."""
    if len(linhas) <= LINHAS_NUMA_COLUNA:
        return linhas
    linhas_da_grade = (len(linhas) + 1) // 2
    return [f'<div class="ar-duas" style="grid-template-rows:repeat({linhas_da_grade},auto)">'
            + "".join(linhas) + "</div>"]


def html_dos_canais(cena: dict[str, Any]) -> str:
    """Uma faixa por aparelho, os mesmos 79 canais, e embaixo os outros dispositivos sem fio.

    Cada linha é ícone · faixa · ponto (desenho aprovado de 05/10/2026). A entrada sem aparelho
    no ar não ganha linha, e o que fica fora da faixa dos controles (o Wi-Fi de 5 GHz) também não.
    """
    if not cena.get("lugares"):
        return ""
    regua = faixas_do_ar.montar(_a_regua_dos_adaptadores(cena),
                                [o for o, _r in _os_outros_radios(cena)])
    rotulos = {o.id: r for o, r in _os_outros_radios(cena)}
    cores, nomes = {faixas_do_ar.RUIDO: "var(--c-ruido)"}, {}
    for _ad, linhas in regua.grupos:
        for linha in linhas:
            cores[linha.id], nomes[linha.id] = _cor_na_regua(linha.tipo, linha.cor), linha.nome
    for linha in regua.outros:
        cores[linha.id], nomes[linha.id] = _cor_na_regua(linha.tipo), linha.nome
    saida = []
    pede = {str(x.get("lugar")) for x in cena.get("pedindo") or ()}
    pulso = (f'<span class="ar-pulso" role="img" title="{PEDINDO_PARA_PAREAR}" '
             f'aria-label="{PEDINDO_PARA_PAREAR}"></span>')
    for ad, linhas in regua.grupos:
        if not linhas and ad.id not in pede:
            continue
        saida.append(f'<div class="ar-grupo cor-{_x(ad.cor)}" data-grupo="{_x(ad.id)}">'
                     f'{_ic("radio", "glifo-do-grupo")}<b>{_x(ad.nome)}</b>'
                     f'{pulso if ad.id in pede else ""}</div>')
        if linhas:
            saida += [f'<div class="ar-do" data-do="{_x(ad.id)}">' + "".join(_em_colunas(
                [_a_linha_do_ar(ln, _o_rotulo_do_aparelho(ln), cores, nomes) for ln in linhas]))
                + "</div>"]
    outros = [ln for ln in regua.outros if ln.sem_faixa != faixas_do_ar.FORA_DA_FAIXA]
    if outros:
        saida.append(f'<div class="ar-grupo outros">{OUTROS_SEM_FIO}</div>'
                     '<div class="ar-do">'
                     + "".join(_a_linha_do_ar(ln, rotulos[ln.id], cores, nomes) for ln in outros)
                     + "</div>")
    return '<div class="ar">' + "".join(saida) + "</div>"



#: A cor de cada tipo na mini-faixa do painel do aparelho (a página do mapa tem a paleta dela).
COR_DA_FAIXA_NO_MAPA = {
    "controle": "#f8f8f2", "celular": "#ff9a8b", "relogio": "#8fa8ff", "fone": "#8be9fd",
    "caixa": "#bd93f9", "teclado": "#ffb86c", "mouse": "#f1fa8c", "wifi": "#c3e88d",
    "ruido": "#8a8fa3", "outro": "#9a9eb8", "adaptador": "#6272a4",
}


def _a_faixa_do_painel(linha: Any, cor_do: dict[str, str], nomes: dict[str, str]) -> dict[str, Any]:
    """A linha da régua na forma do painel: 79 `[estado, cor da marca, nome]` e a frase.

    ``estado``: ``b`` canal bom (pintado), ``p`` perdido (vazio, com a marca de quem o tomou),
    ``o`` ocupado por este aparelho (pintado, com a marca de quem perde ali) e ``l`` livre.
    """
    celulas = []
    for c in linha.celulas:
        if c.estado == faixas_do_ar.PERDIDO:
            celulas.append(["p", cor_do.get(c.dono, cor_do[faixas_do_ar.RUIDO]),
                            nomes.get(c.dono, faixas_do_ar.NOME_DO_RUIDO)])
        elif c.estado == faixas_do_ar.OCUPADO:
            celulas.append(["o", cor_do.get(c.marca, ""), nomes.get(c.marca, "")])
        else:
            celulas.append(["b" if c.estado == faixas_do_ar.BOM else "l", "", ""])
    outro = COR_DA_FAIXA_NO_MAPA["outro"]
    perde = [(n, COR_DA_FAIXA_NO_MAPA.get(t, outro)) for t, n in linha.quem]
    briga = [(nomes[i], cor_do.get(i, outro)) for i in linha.briga if i in nomes]
    # `pedacos`: a frase em `[texto, cor]`, e cada nome leva antes a marca da cor dele, a mesma da
    # célula (o desenho 2: «perde para ■ Wi-Fi · ■ teclado»); a cor nunca vai sozinha, o nome fica
    pedacos: list[list[str]] = []

    def _nomeados(prefixo: str, quem: list[tuple[str, str]], sufixo: str = "") -> None:
        pedacos.append([prefixo, ""])
        for k, (nome, cor) in enumerate(quem):
            pedacos.extend([[" · ", ""]] if k else [])
            pedacos.append([nome, cor])
        if sufixo:
            pedacos.append([sufixo, ""])

    if linha.bons is not None and perde:
        _nomeados("perde para ", perde)
    elif briga:
        ocupados = [c.canal for c in linha.celulas if c.estado == faixas_do_ar.OCUPADO]
        _nomeados("briga com ", briga,
                  f" nos canais {min(ocupados)}-{max(ocupados)}" if ocupados else "")
    if linha.selo is not None:
        selo = " ".join(t for t in (linha.selo.texto, linha.nota) if t)
        # o selo genérico de quem ocupa («briga com N») repetiria a frase que já diz com quem
        if selo and not (briga and linha.bons is None and selo.startswith("briga com")):
            pedacos.append([(" · " if pedacos else "") + selo, ""])
    return {"celulas": celulas, "texto": "".join(t for t, _c in pedacos), "partes": pedacos,
            "cor": cor_do.get(linha.id, cor_do.get(linha.tipo, ""))}


def faixas_para_o_mapa(ctx: Contexto) -> dict[str, dict[str, Any]]:
    """`{vid:pid: faixa}` dos aparelhos do mapa das portas que têm faixa na régua: o rádio
    Bluetooth (o que ele evita) e o receptor ou a placa Wi-Fi (a banda em que ele fala).

    É a MESMA conta da aba 08 (:func:`cena_do_radio` e `faixas_do_ar.montar`): uma faixa só, dita
    nos dois lugares. Sem leitura, o aparelho não ganha faixa — ausência é resposta.
    """
    cena = cena_do_radio(ctx)
    adaptadores = _a_regua_dos_adaptadores(cena)
    ocupantes = [o for o, _r in _os_outros_radios(cena)]
    regua = faixas_do_ar.montar(adaptadores, ocupantes)
    cor_do = dict(COR_DA_FAIXA_NO_MAPA)
    nomes = {faixas_do_ar.RUIDO: faixas_do_ar.NOME_DO_RUIDO}
    for linha in regua.todas():
        cor_do[linha.id] = COR_DA_FAIXA_NO_MAPA.get(linha.tipo, COR_DA_FAIXA_NO_MAPA["outro"])
        nomes[linha.id] = linha.nome
    cor_do[faixas_do_ar.RUIDO] = COR_DA_FAIXA_NO_MAPA["ruido"]
    saida: dict[str, dict[str, Any]] = {}
    for linha in regua.outros:
        if linha.celulas:
            saida[linha.id] = _a_faixa_do_painel(linha, cor_do, nomes)
    por_lugar = {str(lug["id"]): str(lug.get("modelo") or "") for lug in cena.get("lugares") or ()}
    for adaptador in adaptadores:
        modelo = por_lugar.get(adaptador.id, "")
        propria = faixas_do_ar.linha_do_adaptador(adaptador, ocupantes)
        if modelo and propria.celulas:
            faixa = _a_faixa_do_painel(propria, cor_do, nomes)
            faixa["cor"] = COR_DA_FAIXA_NO_MAPA["controle"]
            saida.setdefault(modelo, faixa)
    return saida


_SALA_NA_TELA: dict[str, str] = {}


def _sem_o_que_pisca(cena: dict[str, Any]) -> dict[str, Any]:
    """A cena sem a varredura, a busca, o «ocupado» e o nível do movimento — o"""
    return {**cena, "ocupado": False, "niveis": {}, "dicas": {},
            "lugares": [{**lug, "varrendo": False, "conectando": False}
                        for lug in cena.get("lugares") or ()]}


def _sala_estavel(cena: dict[str, Any]) -> str:
    """A sala, que SÓ MUDA quando mudam as caixas ou os aparelhos dentro delas."""
    chave = html_da_sala(_sem_o_que_pisca(cena))
    if _SALA_NA_TELA.get("chave") != chave:
        _SALA_NA_TELA.update(chave=chave, html=html_da_sala(cena))
    return _SALA_NA_TELA["html"]


_NIVEL_NA_TELA: dict[str, tuple[str, float]] = {}
_RELOGIO_DO_NIVEL: Callable[[], float] = time.monotonic
_ORDEM_DO_NIVEL = {"": -1, NIVEL_ENGASGA: 0, NIVEL_MEDIO: 1, NIVEL_LISO: 2}


def _nivel_seguro(uniq: str, nivel: str, agora: float) -> str:
    """A COR PIORA NA HORA E MELHORA DEVAGAR (O-HZ-TEM-A-COR-DA-DISTANCIA-01)."""
    antes = _NIVEL_NA_TELA.get(uniq)
    if (antes is None or not nivel or not antes[0]
            or _ORDEM_DO_NIVEL[nivel] <= _ORDEM_DO_NIVEL[antes[0]]
            or agora - antes[1] >= SEGURA_O_NIVEL_S):
        _NIVEL_NA_TELA[uniq] = (nivel, agora)
        return nivel
    return antes[0]


#: A referência do Hz é do controle NAQUELE adaptador: a chave é `(controle, adaptador)`, e
#: o controle que muda de adaptador recomeça a dele.
_REFERENCIA_DO_HZ: dict[tuple[str, str], tuple[int, float, float]] = {}
_CAUSA_NA_TELA: dict[str, tuple[str, str]] = {}


def _diagnostico_do_controle(a: dict[str, Any], controles: list[dict[str, Any]],
                             cena: dict[str, Any], segurar: bool, agora: float) -> Diagnostico:
    """O nível e a causa do movimento de UM controle: o Hz contra o que ELE dava ali, e o sinal."""
    lugar = str(a.get("lugar") or "")
    uid = str(a["id"])
    referencia = a.get("hz_referencia")
    if referencia is None and segurar and a.get("hz_mov") is not None:
        dividem = sum(1 for o in controles if str(o.get("lugar") or "") == lugar
                      and not o.get("usb"))
        chave = (uid, lugar)
        for outra in [k for k in _REFERENCIA_DO_HZ if k[0] == uid and k != chave]:
            del _REFERENCIA_DO_HZ[outra]
        _REFERENCIA_DO_HZ[chave] = atualizar_a_referencia(
            _REFERENCIA_DO_HZ.get(chave), dividem, a["hz_mov"], agora)
        referencia = _REFERENCIA_DO_HZ[chave][1]
    return diagnosticar_o_movimento(
        a.get("hz_mov"), sinal_dbm=a.get("sinal"), referencia_hz=referencia,
        via_radio=not a.get("usb"),
        adaptador_cheio=len(_pontes(cena, lugar)) > PONTES_POR_ADAPTADOR)


def _niveis_e_dicas(controles: list[dict[str, Any]], cena: dict[str, Any], segurar: bool,
                    agora: float) -> tuple[list[str], list[str]]:
    """`(níveis, frases)` na ordem dos controles; a cor segura o pior e a frase vai junto."""
    niveis: list[str] = []
    dicas: list[str] = []
    for a in controles:
        uid = str(a["id"])
        d = _diagnostico_do_controle(a, controles, cena, segurar, agora)
        nivel, causa = d.nivel, d.causa
        if segurar:
            nivel = _nivel_seguro(uid, d.nivel, agora)
            if nivel == d.nivel:
                _CAUSA_NA_TELA[uid] = (nivel, d.causa)
            else:
                causa = _CAUSA_NA_TELA.get(uid, (nivel, ""))[1]
        niveis.append(nivel)
        dicas.append(dica_do_movimento(nivel, causa))
    return niveis, dicas


def campos_da_secao(cena: dict[str, Any], *, segurar: bool = False) -> dict[str, Any]:
    """O que o pacote emite para a seção, NA ORDEM: a sala antes dos Hz e das"""
    controles = [a for lug in cena.get("lugares", ()) for a in _moradores(cena, str(lug["id"]))
                 if a.get("tipo") == "controle" and not a.get("esperando") and _no_ar(a)]
    com_mic = [a for a in controles if a.get("mic")]
    lugares = list(cena.get("lugares") or ())
    agora = _RELOGIO_DO_NIVEL()
    niveis, dicas = _niveis_e_dicas(controles, cena, segurar, agora)
    if segurar:
        for saiu in set(_NIVEL_NA_TELA) - {str(a["id"]) for a in controles}:
            del _NIVEL_NA_TELA[saiu]
            _CAUSA_NA_TELA.pop(saiu, None)
            for chave in [k for k in _REFERENCIA_DO_HZ if k[0] == saiu]:
                del _REFERENCIA_DO_HZ[chave]
    cena = {**cena, "niveis": {str(a["id"]): n for a, n in zip(controles, niveis, strict=True)},
            "dicas": {str(a["id"]): d for a, d in zip(controles, dicas, strict=True)}}
    return {
        "radio-sala": _sala_estavel(cena),
        "radio-varrendo": ["sim" if lug.get("varrendo") else "" for lug in lugares],
        "radio-conectando": ["sim" if lug.get("conectando") else "" for lug in lugares],
        "radio-procurando": str(cena.get("procurando") or TRAVESSAO_DO_PROCURAR),
        "radio-moldes": html_dos_moldes(cena),
        "hz-movimento": [_hz(a.get("hz_mov")) for a in controles],
        "hz-nivel": niveis,
        "hz-dica": dicas,
        "hz-voz": [_hz(a.get("hz_voz")) for a in com_mic],
        "espectro-canais": html_dos_canais(cena),
        "radio-ocupado": "sim" if _ocupado(cena) else "",
    }


# `state_full` (o BlueZ, o diário, o `kernel.log`, o `maquina.json`) é lido num

_FUNDO: dict[str, tuple[float, Any]] = {}
_FUNDO_EM_VOO: set[str] = set()
_TRAVA_DO_FUNDO = threading.Lock()
_GERACAO: dict[str, int] = {}
LER_NA_HORA = False
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
        except Exception:
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
    """Depois de um gesto que grava, a próxima volta lê de novo."""
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


def _ler_o_wifi() -> list[dict[str, Any]] | None:
    """As redes sem fio ativas e a faixa de cada uma; `None` quando nada se lê."""
    perfil._com_o_src()
    redes = faixa_do_wifi.ler_as_redes()
    if redes is None:
        return None
    return [{"no": r.no, "mhz": r.frequencia_mhz, "largura": r.largura_mhz,
             "chave": r.chave} for r in redes]


def _ler_as_quedas() -> dict[str, Any] | None:
    """As quedas do barramento deste boot, por `usb:vid:pid` (o diário do kernel, em fundo)."""
    perfil._com_o_src()
    return queda_do_wifi.ler_as_quedas()


def _o_wifi_com_as_quedas(
    redes: list[dict[str, Any]], quedas: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Cada rede lida, com o que o diário diz da placa dela (`quedas`: `{n, min}`)."""
    saida = []
    for rede in redes:
        q = (quedas or {}).get(str(rede.get("chave") or ""))
        saida.append({**rede, "quedas": {"n": q.n, "min": q.minutos}} if q is not None
                     else dict(rede))
    return saida


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
    """`{endereço: [{quando, porque, carimbo}]}` — o sino de cada adaptador, pela hora."""
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


def _tipo_pela_classe(classe: int | None) -> str:
    if not isinstance(classe, int):
        return "outro"
    maior, menor = (classe >> 8) & 0x1F, (classe >> 2) & 0x3F
    if maior == 0x02:
        return "celular"
    if maior == 0x04:
        return "fone" if menor in (0x01, 0x06) else "caixa"
    if maior == 0x05:
        return {0x10: "teclado", 0x20: "mouse", 0x30: "teclado"}.get(menor & 0x30, "outro")
    if maior == 0x06 and menor & 0x08:
        return "webcam"
    if maior == 0x07:
        return "relogio"
    return "outro"


def _tipo_pela_aparencia(aparencia: int | None) -> str:
    """O tipo pela ``Appearance`` do GAP (a categoria são os 10 bits de cima): é o que um
    relógio ou uma pulseira LE tem quando o BlueZ não lhes dá ``Icon`` nem ``Class``."""
    if not isinstance(aparencia, int) or isinstance(aparencia, bool):
        return "outro"
    return {0x01: "celular", 0x03: "relogio"}.get(aparencia >> 6, "outro")


def _tipo_do_aparelho(icone: str, classe: int | None, aparencia: int | None = None) -> str:
    """O tipo pelo ``Icon`` do BlueZ primeiro, depois pela classe e pela aparência."""
    pelo_icone = TIPO_PELO_ICONE.get(str(icone or ""))
    if pelo_icone:
        return pelo_icone
    pela_classe = _tipo_pela_classe(classe)
    return pela_classe if pela_classe != "outro" else _tipo_pela_aparencia(aparencia)


_NOMES_DE_FABRICA = ("DualSense", "Wireless Controller")


def _e_nome_de_fabrica(nome: str) -> bool:
    return any(nome.startswith(f) for f in _NOMES_DE_FABRICA)


_ALIAS_QUE_E_ENDERECO = re.compile(r"[0-9A-Fa-f]{2}([-:_][0-9A-Fa-f]{2}){5}")


def _quem_pede_para_parear(central: dict[str, Any], lugares: list[dict[str, Any]],
                           aparelhos_bz: tuple[Any, ...]) -> list[dict[str, str]]:
    """Os controles conhecidos que pedem para parear (``radio_central.pedindo``), na tela.

    O dono do sinal é a central (conhecido + desconectado + ouvido na varredura); aqui só se
    dá o nome dela e o adaptador que o ouve. O nome de fábrica vira «Controle».
    """
    ids = {str(lug["id"]) for lug in lugares}
    nomes = _nomes_por_endereco(aparelhos_bz)
    saida = []
    for x in central.get("pedindo") or ():
        if not isinstance(x, dict):
            continue
        aparelho, lugar = _mac(x.get("aparelho")), _mac(x.get("adaptador"))
        if not aparelho or lugar not in ids:
            continue
        alias = str(x.get("nome") or "").strip()
        dado = nomes.get(aparelho) or (
            nome_dado(alias) if alias and not _e_nome_de_fabrica(alias)
            and not _ALIAS_QUE_E_ENDERECO.fullmatch(alias) else "")
        saida.append({"aparelho": aparelho, "lugar": lugar, "nome": dado or CONTROLE_SEM_NOME})
    return saida


def _nomes_por_endereco(aparelhos_bz: tuple[Any, ...]) -> dict[str, str]:
    """O nome que ela deu a cada controle, pelo ENDEREÇO — um só por aparelho."""
    nomes: dict[str, str] = {}
    for a in sorted(aparelhos_bz, key=lambda a: getattr(a, "conectado", None) is not True):
        nome = str(getattr(a, "nome", "") or "").strip()
        endereco = _mac(getattr(a, "endereco", ""))
        if (nome and endereco and not _e_nome_de_fabrica(nome)
                and not _ALIAS_QUE_E_ENDERECO.fullmatch(nome) and endereco not in nomes):
            nomes[endereco] = nome_dado(nome) if _e_controle_do_bluez(a) else nome
    return nomes


def _modelo_do_radio(radio: Any) -> str:
    """`vid:pid` do rádio USB (a chave do que o mapa das portas sabe dele), ou `""`."""
    vid, pid = str(getattr(radio, "vid", "") or ""), str(getattr(radio, "pid", "") or "")
    return f"{vid}:{pid}" if vid or pid else ""


def cena_do_radio(ctx: Contexto) -> dict[str, Any]:
    """A cena da seção pela máquina do usuário — os donos, e nada estimado (R10)."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import entrada_a_entrada
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig, nome_dado_ao_adaptador

    st: dict[str, Any] = ctx.state or {}
    ar: dict[str, Any] = _dicionario(st.get("radio_ar"))
    governador: dict[str, Any] = _dicionario(st.get("radio_governador"))
    central: dict[str, Any] = _dicionario(st.get("radio_central"))
    bluez = _em_fundo("bluez", _ler_o_bluez, 3.0)
    lida = _em_fundo("maquina", _ler_a_maquina, 5.0)
    wifi = _o_wifi_com_as_quedas(_em_fundo("wifi", _ler_o_wifi, 10.0) or [],
                                 _em_fundo("wifi-quedas", _ler_as_quedas, 30.0))
    maquina, controladores = lida if lida else (None, {})
    if _DESCOBERTA.ativa:
        # o «Descobrir a faixa» anda pelo censo, e o censo da porta é lido uma vez e no
        # «Examinar»: com o gesto em curso ele se relê no fundo, senão o receptor tirado
        # continuaria «na porta» até o gesto se desfazer sozinho
        _em_fundo("mesa-do-gesto", lambda: _mesa_do_radio(recarregar=True),
                  RELER_A_PORTA_NO_GESTO_S)
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
    movimentos = [m for m in central.get("movimentos") or () if isinstance(m, dict)]
    busca = central.get("busca") if isinstance(central.get("busca"), dict) else None
    busca_em = _mac(busca.get("adaptador")) if busca else ""
    esperando = [m for m in movimentos if _ainda_espera(m, agora, busca_em)]
    ocupado = bool(esperando)

    apertadas = {n for par in getattr(mesa, "apertadas", ()) or () for n in par}

    lugares: list[dict[str, Any]] = []
    caminho_para_endereco: dict[str, str] = {}
    evitados: list[dict[str, Any]] = []
    canais_medidos: dict[str, bool] = {}
    enlaces: dict[str, dict[str, Any]] = {}
    portas: list[dict[str, Any]] = []
    for end in enderecos:
        bz = bz_de.get(end)
        mz = por_hci.get(str(getattr(bz, "hci", ""))) if bz is not None else None
        lugar = str(getattr(bz, "lugar", "") or getattr(mz, "lugar", "") or "")
        caminho = str(getattr(mz, "caminho", "") or "")
        if caminho:
            caminho_para_endereco[caminho] = end
        documento = maquina if maquina is not None else MaquinaConfig()
        entrada = entrada_a_entrada.rotulo_da_entrada(
            lugar, maquina=documento, controladores=controladores) if lugar else None
        face = entrada_a_entrada.face_do_lugar(
            lugar, maquina=documento, controladores=controladores) if lugar else None
        publicado = ar.get(end) or next((v for k, v in ar.items() if _mac(k) == end), None) or {}
        lista = publicado.get("canais_evitados") if isinstance(publicado, dict) else None
        if isinstance(publicado, dict) and isinstance(publicado.get("enlaces"), dict):
            enlaces[end] = publicado["enlaces"]
        if isinstance(lista, list):
            canais_medidos[end] = True
            evitados.extend({"lugar": end, "ini": a, "fim": b} for a, b in _faixas(lista))
        junto = ""
        no = str(getattr(mz, "no", "") or "")
        if no and no in apertadas:
            junto = "colado em outro rádio"
        lugares.append({
            "id": end, "lugar": lugar,
            "nome": nome_dado(nome_dado_ao_adaptador(maquina, end)),
            "entrada": entrada or (DENTRO_DA_MAQUINA if bz is not None else ""),
            "sabido": bz is not None and maquina is not None,
            "face": face or "",
            "hub": bool(getattr(mz, "atras_de_hub", False)),
            "varrendo": bool(getattr(bz, "varrendo", False)) and end != busca_em,
            "junto": junto, "usb3": False,
            "modelo": _modelo_do_radio(mz),
            "conectando": bool(busca_em) and end == busca_em,
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

    endereco_do_caminho = {str(getattr(a, "caminho", "")): _mac(a.endereco)
                           for a in adaptadores_bz}
    aparelhos = _aparelhos_da_cena(ctx, st, governador, esperando, aparelhos_bz,
                                   endereco_do_caminho, enderecos)
    no_ar = (frozenset(_so_hex(a.endereco) for a in aparelhos_bz if a.conectado is True)
             | frozenset(_so_hex(str(c.get("uniq") or "")) for c in ctx.conectados))
    pareados = frozenset((endereco_do_caminho.get(str(a.adaptador), ""), _mac(a.endereco))
                         for a in aparelhos_bz if a.pareado)
    falhas = _os_que_nao_conectaram(ctx, movimentos, agora, enderecos, no_ar, pareados)
    falhas += _os_que_nao_viraram_controle(
        _em_fundo("zumbis", _ler_os_zumbis, 2.0), enderecos, falhas, time.monotonic())
    aparelhos += falhas
    no_usb = frozenset(_so_hex(str(c.get("uniq") or "")) for c in ctx.conectados
                       if str(c.get("transport") or "").lower() == "usb")
    aparelhos += _os_desligados(aparelhos_bz, endereco_do_caminho, aparelhos, no_usb)
    for lug in lugares:
        lug["nao_conectou"] = any(f["lugar"] == lug["id"] for f in falhas)
    declaracao_viva = _declaracao()
    declarados = _radios_declarados(declaracao_viva)
    para_id, rotulo_do_tipo = _tipos_de_radio()
    receptores = _dicionario(st.get("radio_receptores"))
    na_porta = (None if mesa is None else
                any(_chave_do_radio(r) == _DESCOBERTA.chave
                    for r in getattr(mesa, "radios", ()) or ()))
    _andar_a_descoberta(ar, time.monotonic(), na_porta)
    vizinhos = []
    for r in getattr(mesa, "radios", ()) or ():
        chave = _chave_do_radio(r)
        tipo = declarados.get(chave, "")
        no_do_radio = str(getattr(r, "no", "") or "")
        sugestao = "" if tipo else _sugestao_do_vizinho(no_do_radio, para_id)
        vizinhos.append({"id": chave, "tipo": tipo, "nome": rotulo_do_tipo.get(tipo, ""),
                         "sugestao": sugestao, "sugestao_tipo": para_id.get(sugestao, ""),
                         "no": no_do_radio, "lido": "" if tipo else _lido_do_kernel(no_do_radio),
                         "produto": "" if tipo else _produto_do_no(no_do_radio),
                         "receptor": _e_um_receptor(no_do_radio),
                         "banda": _banda_declarada(declaracao_viva, chave),
                         "saude": receptores.get(f"usb:{chave}")})
        if getattr(r, "caminho", ""):
            portas.append({"id": f"porta-{chave}", "caminho": str(r.caminho),
                           "usb": "3.0" if getattr(r, "usb3", False) else "2.0",
                           "ocupa": chave, "grupo": _grupo_da_porta(str(r.caminho)),
                           "rotulo": str(r.caminho)})
    if _DESCOBERTA.ativa:
        visto = next((v for v in vizinhos if v["id"] == _DESCOBERTA.chave), None)
        if visto is not None:
            _VISTO_NO_GESTO.update({_DESCOBERTA.chave: visto})
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
    pedindo = _quem_pede_para_parear(central, lugares, aparelhos_bz)
    proposta = central.get("proposta") if isinstance(central.get("proposta"), dict) else None
    if proposta:
        dono = next((a for a in aparelhos
                     if _so_hex(a["id"]) == _so_hex(str(proposta.get("controle") or ""))), None)
        proposta = ({"controle": dono["id"], "destino": _mac(proposta.get("destino"))}
                    if dono else None)
    lugares = _na_ordem_dela(lugares)
    buscas: dict[str, object] = {
        _mac(m.get("destino")): (str(m.get("aparelho") or ""), float(m.get("quando") or 0.0))
        for m in esperando if _mac(m.get("destino"))}
    cena = {
        # `radio_ar`/`radio_governador`. Sem isso a sala não diz «nenhum».
        "lido": bluez is not None or bool(ar) or bool(governador),
        "lugares": lugares, "aparelhos": aparelhos, "evitados": evitados,
        "canais_medidos": canais_medidos, "enlaces": enlaces, "vizinhos": vizinhos,
        "descobrindo_ausente": _o_receptor_tirado(vizinhos),
        "wifi": wifi,
        "portas": portas, "pedido": pedido, "proposta": proposta, "ocupado": ocupado,
        "pedindo": pedindo,
        "passo_da_espera": next((str(m.get("passo") or "") for m in esperando), ""),
        "procurando": (TRAVESSAO_DO_PROCURAR if not isinstance(st.get("radio_central"), dict)
                       else PROCURAR_LIGADO if busca_em else PROCURAR_DESLIGADO),
        "aberto": _o_aberto(lugares, aparelhos, proposta),
        "perto": _perto(aparelhos_bz, adaptadores_bz, aparelhos, buscas),
    }
    cena["destino_da_central"] = _destino_da_central(cena, st)
    cena["destino_do_conectar"] = _destino_do_conectar(cena)
    return cena


def _onde_espera(lugares: list[dict[str, Any]], aparelhos: list[dict[str, Any]]) -> str | None:
    """O adaptador em que um movimento espera o gesto do usuário — onde a busca ESTÁ."""
    return next((str(a["lugar"]) for a in aparelhos if a.get("esperando") and a.get("lugar")),
                None) or next((str(lug["id"]) for lug in lugares if lug.get("conectando")), None)


def _o_aberto(lugares: list[dict[str, Any]], aparelhos: list[dict[str, Any]],
              proposta: dict[str, Any] | None = None) -> str | None:
    """O adaptador aberto no acordeão."""
    if len(lugares) == 1:
        return str(lugares[0]["id"])
    escolhido = _ABERTO.get("lugar", "")
    if escolhido is None or escolhido in {str(lug["id"]) for lug in lugares}:
        return str(escolhido) if escolhido else None
    espera = _onde_espera(lugares, aparelhos)
    if espera:
        return espera
    # as caixas nascem fechadas (desenho aprovado de 05/10/2026): abre a que ela clicar, ou a
    # que pede atenção (o controle esperando, o que não conectou)
    return next((str(lug["id"]) for lug in lugares if lug.get("nao_conectou")), None)


def _chave_da_ordem(endereco: object) -> str:
    """A chave do adaptador na ordem gravada: o ENDEREÇO, a chave dele em"""
    perfil._com_o_src()
    from hefesto_dualsense4unix.utils.maquina import chave_do_adaptador

    return chave_do_adaptador(endereco) or ""


def _na_ordem_dela(lugares: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Os adaptadores na ORDEM QUE ELA ARRASTOU — decisão, 25/09/2026, e a ordem fica gravada no
    adaptador, pelo endereço
    (``utils/maquina.AdaptadorDeclarado.ordem``). Quem ela nunca arrastou vem
    depois, na ordem de sempre. <!-- noqa-acento: citação literal -->

    A ordem que ela arrastou antes de 28/09/2026 morava no ``gui_prefs``, pela
    chave do lugar; ela vale, traduzida pelos adaptadores da tela, até ela
    arrastar de novo (:func:`_a_ordem_de_antes`).
    """
    try:
        ordem = [_chave_da_ordem(chave) for chave in _ordem_gravada()]
        ordem = [chave for chave in ordem if chave] or _a_ordem_de_antes(lugares)
    except Exception:
        ordem = []
    if not ordem:
        return lugares
    posicao = {chave: i for i, chave in enumerate(ordem)}
    return sorted(
        lugares, key=lambda lug: posicao.get(_chave_da_ordem(lug.get("id")), len(posicao)))


def _ordem_gravada() -> list[str]:
    """A ordem do dono, lida NA HORA: o arrastar reordena a sala no tique"""
    perfil._com_o_src()
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, ordem_dos_adaptadores

    return ordem_dos_adaptadores(carregar_maquina())


def _a_ordem_de_antes(lugares: list[dict[str, Any]]) -> list[str]:
    """A lista do ``gui_prefs`` de antes de 28/09/2026 — pelo LUGAR de cada
    adaptador (ou pelo endereço do que não tem porta) —, traduzida para o
    endereço de quem está na tela. Só leitura: quem a leva ao dono é o
    arrastar (:func:`adaptador_reordenar`)."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.gui_prefs import a_ordem_dos_adaptadores_de_antes

    de_antes = a_ordem_dos_adaptadores_de_antes()
    if not de_antes:
        return []
    por_chave: dict[str, str] = {}
    for lug in lugares:
        chave = _chave_da_ordem(lug.get("id"))
        for antiga in (str(lug.get("lugar") or ""), str(lug.get("id") or "")):
            if antiga and chave:
                por_chave.setdefault(antiga, chave)
    return list(dict.fromkeys(por_chave[c] for c in de_antes if c in por_chave))


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


def _ainda_espera(m: dict[str, Any], agora: float, busca_em: str = "") -> bool:
    """Este movimento ainda segura a tela: «esperando», e há menos de"""
    if m.get("estado") != "esperando":
        return False
    if not m.get("aparelho") and busca_em:
        return True
    return agora - float(m.get("quando") or 0.0) <= ESPERA_NA_TELA_S


_NAO_CHEGOU_NA_CENTRAL = "nao_chegou"  # (noqa-acento): chave de máquina da central
_RECUSA_DA_CENTRAL = "ocupado"
_DISPENSADOS: set[str] = set()


def _os_que_nao_conectaram(ctx: Contexto, movimentos: list[dict[str, Any]], agora: float,
                           enderecos: list[str],
                           no_ar: frozenset[str] = frozenset(),
                           pareados: frozenset[tuple[str, str]] = frozenset(),
                           ) -> list[dict[str, Any]]:
    """A linha «Não Conectou» de cada APARELHO que não chegou e não está no ar.

    Não chegou é a central dizendo «não chegou» (qualquer motivo, menos a
    recusa do um-por-vez, que não começou nada, e a busca que ela desligou),
    ou o «esperando» que passou de :data:`ESPERA_NA_TELA_S`.

    A LINHA TEM APARELHO (ESQUECER-E-LIMPAR-AS-CONEXOES-01,
    D-3009-A-LINHA-TEM-APARELHO, 30/09/2026, a validar pelo usuário).
    A busca que ninguém respondeu (o movimento sem endereço) virava «DualSense ·
    Não Conectou», com o desenho do controle, a borda laranja e a caixa que
    abria — o *«controle fantasma»* dela. Agora a linha só existe enquanto há um
    aparelho de verdade que não chegou e que não está no ar em adaptador
    nenhum, por nenhum transporte (``no_ar``: o ``Connected`` do BlueZ e o
    ``uniq`` que o daemon publica, o cabo também): ela some no tique em que ele
    aparece. Uma por aparelho, como a central guarda — o «Conectar» que vem
    depois no mesmo adaptador não apaga a linha de quem ficou sem casa. O fim
    da busca sem ninguém é dito onde a busca mora: no «Procurar».
    <!-- noqa-acento: citação literal -->

    A MEIA CHAVE É DA CENTRAL, E A TELA SÓ MOSTRA (achado 8 da auditoria de
    26/09, A-CAIXA-FICA-ONDE-ELA-ABRIU-01). Quem tira a chave do ``Pair`` que
    não conectou é a central, antes de publicar o «não chegou»
    (``central_do_radio._esquecer_a_meia_chave``), e quem tira a linha é o X
    dela, na central (``radio.dispensar``).
    """
    da_mesa = {_so_hex(str(e.get("uniq") or "")): e for e in ctx.mesa}
    linhas: list[dict[str, Any]] = []
    for m in movimentos:
        aparelho = _mac(m.get("aparelho")) if m.get("aparelho") else ""
        destino = _mac(m.get("destino"))
        if not aparelho or destino not in enderecos or _so_hex(aparelho) in no_ar:
            continue
        idade = agora - float(m.get("quando") or 0.0)
        estado = str(m.get("estado") or "")
        motivo = str(m.get("motivo") or "")
        falhou = ((estado == _NAO_CHEGOU_NA_CENTRAL
                   and motivo not in (_RECUSA_DA_CENTRAL, _central_do_radio.MOTIVO_DESLIGADA))
                  or (estado == "esperando" and idade > ESPERA_NA_TELA_S))
        if not falhou or idade > LEMBRA_O_NAO_CONECTOU_S:
            continue
        eu = da_mesa.get(_so_hex(aparelho), {})
        classe = m.get("classe")
        tipo = ("controle" if m.get("e_controle", True)
                else _tipo_do_aparelho(str(m.get("icone") or ""),
                                       classe if isinstance(classe, int) else None))
        cor = _hex_do_plastico(str(eu.get("cor") or ""))
        linhas.append({
            "id": f"nao-conectou-{_so_hex(destino)}-{_so_hex(aparelho)}", "aparelho": aparelho,
            "tipo": tipo, "lugar": destino, "nome": str(m.get("nome") or ""),
            "modalias": str(m.get("modalias") or ""), "jogador": eu.get("jogador"),
            "rotulo": ("DualSense" if tipo == "controle"
                       else PALAVRA_DO_TIPO.get(tipo, "aparelho").capitalize()),
            "cor": cor if cor.startswith("#") else "",
            "cor_nome": "" if str(eu.get("nome") or "") in ("", _cor_desconhecida())
            else str(eu["nome"]),
            "nao_conectou": True, "esperando": False, "fixo": True,
            "pareado_aqui": (destino, aparelho) in pareados,
        })
    return linhas


def _ler_os_zumbis() -> dict[str, Any]:
    """A última volta do vigia de zumbis, do arquivo que ele grava a cada volta."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.daemon.subsystems.conexoes import ler_o_diario

    return ler_o_diario()


def _os_que_nao_viraram_controle(diario: dict[str, Any] | None, enderecos: list[str],
                                 falhas: list[dict[str, Any]],
                                 agora: float) -> list[dict[str, Any]]:
    """A linha «Não Conectou» do controle que conectou no rádio e NÃO virou controle."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.daemon.subsystems.conexoes import INTERVALO_S

    volta = diario if isinstance(diario, dict) else {}
    carimbo = volta.get("carimbo")
    idade = agora - float(carimbo) if isinstance(carimbo, int | float) else -1.0
    fresca = 0.0 <= idade <= VOLTAS_DO_VIGIA_NA_TELA * INTERVALO_S

    def pares(chave: str) -> list[tuple[str, str]]:
        return [(_mac(link.get("adaptador")), _so_hex(str(link.get("controle") or "")))
                for link in volta.get(chave) or () if isinstance(link, dict)]

    derrubados = set(pares("derrubados")) if fresca else set()
    presos = [par for par in (pares("zumbis") if fresca else [])
              if par not in derrubados and par[0] in enderecos and par[1]]
    chaves = {f"zumbi|{lugar}|{quem}" for lugar, quem in presos}
    if fresca:
        for velha in [c for c in _DISPENSADOS if c.startswith("zumbi|") and c not in chaves]:
            _DISPENSADOS.discard(velha)
    ja = {(str(f.get("lugar") or ""), _so_hex(str(f.get("aparelho") or ""))) for f in falhas}
    linhas: list[dict[str, Any]] = []
    vistos: set[tuple[str, str]] = set()
    for lugar, quem in presos:
        chave = f"zumbi|{lugar}|{quem}"
        if (lugar, quem) in ja or (lugar, quem) in vistos or chave in _DISPENSADOS:
            continue
        vistos.add((lugar, quem))
        linhas.append({
            "id": f"nao-virou-{_so_hex(lugar)}-{quem}", "aparelho": "",
            "tipo": "controle", "lugar": lugar, "nome": "", "modalias": "",
            "jogador": None, "rotulo": "DualSense", "cor": "", "cor_nome": "",
            "nao_conectou": True, "chave": chave, "esperando": False, "fixo": True,
        })
    return linhas


def _e_controle_do_bluez(a: Any) -> bool:
    """Pergunta à CLASSE (o dono é `gesto_de_pareamento.e_controle`), e sem ela"""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.gesto_de_pareamento import e_controle

    classe = getattr(a, "classe", None)
    if classe is not None:
        return e_controle(classe)
    icone = str(getattr(a, "icone", "") or "")
    if icone:
        return icone == "input-gaming"
    return "V054C" in str(getattr(a, "modalias", "") or "").upper()


def _os_desligados(aparelhos_bz: tuple[Any, ...], endereco_do_caminho: dict[str, str],
                   ja: list[dict[str, Any]],
                   no_usb: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """Os aparelhos com pareamento NESTE adaptador e fora do ar — o item 3: o"""
    no_ar = {_so_hex(a.endereco) for a in aparelhos_bz if a.conectado is True}
    vivos = {_so_hex(str(a["id"])) for a in ja if not a.get("nao_conectou")}
    falhas = {(_so_hex(str(a.get("aparelho") or "")), a["lugar"])
              for a in ja if a.get("nao_conectou")}
    nomes = _nomes_por_endereco(aparelhos_bz)
    vistos: set[tuple[str, str]] = set()
    fora: list[dict[str, Any]] = []
    for a in aparelhos_bz:
        lugar = endereco_do_caminho.get(str(a.adaptador), "")
        h = _so_hex(a.endereco)
        if (a.pareado is not True or a.conectado is True or not lugar or h in no_ar
                or h in vivos or (h, lugar) in falhas or (h, lugar) in vistos):
            continue
        vistos.add((h, lugar))
        alias = str(a.nome or "")
        alias = "" if _ALIAS_QUE_E_ENDERECO.fullmatch(alias) else alias
        if _e_controle_do_bluez(a):
            tipo, nome = "controle", nomes.get(_mac(a.endereco), "")
            rotulo = alias if alias and not _e_nome_de_fabrica(alias) else "DualSense"
        else:
            tipo = _tipo_do_aparelho(str(getattr(a, "icone", "") or ""), a.classe,
                                     getattr(a, "aparencia", None))
            nome, rotulo = alias, alias or PALAVRA_DO_TIPO.get(tipo, "aparelho").capitalize()
        fora.append({
            "id": _mac(a.endereco), "aparelho": _mac(a.endereco), "tipo": tipo,
            "lugar": lugar, "nome": nome, "rotulo": rotulo,
            "modalias": str(a.modalias or ""), "desligado": True,
            "usb": tipo == "controle" and h in no_usb, "esperando": False, "fixo": True,
        })
    return fora


def _com_dois_pontos(valor: object) -> str:
    """``AABBCC0000A1`` ou ``aa:bb:…`` → ``aa:bb:cc:00:00:a1``; ``""`` sem forma."""
    h = _so_hex(str(valor or ""))
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else ""


def _esquecer_o_pareamento(lugar: str, aparelho: str) -> Any:
    """O pareamento de ``aparelho`` em ``lugar`` sai — pelo dono do «Esquecer»"""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import gesto_de_pareamento

    return gesto_de_pareamento.esquecer_o_pareamento(
        _com_dois_pontos(lugar), _com_dois_pontos(aparelho), quem="tela")


def _aparelhos_da_cena(ctx: Contexto, st: dict[str, Any], governador: dict[str, Any],
                       esperando: list[dict[str, Any]], aparelhos_bz: tuple[Any, ...],
                       endereco_do_caminho: dict[str, str],
                       enderecos: list[str]) -> list[dict[str, Any]]:
    """Os controles pelo `state_full` (as quatro chaves por controle) e o resto pelo BlueZ."""
    da_mesa = {str(m.get("uniq") or ""): m for m in ctx.mesa}
    alem = {_so_hex(str(p.get("uniq") or "")): (p.get("tipo"), bool(p.get("alem_do_limite")))
            for publicado in governador.values()
            for p in _dicionario(publicado).get("pontes") or ()}
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
            "jogador": eu.get("jogador"),
            "rotulo": f"Player {eu['jogador']}" if eu.get("jogador") else "DualSense",
            "cor": cor if cor.startswith("#") else "",
            "cor_nome": "" if str(eu.get("nome") or "") in ("", _cor_desconhecida())
            else str(eu["nome"]),
            "mic": (not audio.get("mic_mudo")) if "mic_mudo" in audio
            else bool(c.get("hz_voz")),
            "ponte": ponte if ponte in ("som", "haptica") else None, "alem": passou,
            "hz_mov": c.get("hz_movimento"), "hz_voz": c.get("hz_voz"), "luz": True,
            "sinal": c.get("sinal_dbm"),
            "esperando": False, "fixo": False,
        })
        vistos.add(_so_hex(uniq))
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
        # «outro» — e o controle, um DualSense sem nome. O `Icon` vem junto: é o
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
                     "tipo": _tipo_do_aparelho(getattr(a, "icone", ""), a.classe,
                                               getattr(a, "aparencia", None)),
                     "lugar": adaptador,
                     "nome": str(a.nome or ""), "rotulo": str(a.nome or ""),
                     "pareado": a.pareado is True,
                     "esperando": False, "fixo": False})
        vistos.add(_so_hex(endereco))
    return fora


_CHEGADAS: dict[str, tuple[object, dict[str, int]]] = {}
_NUMERO_DA_CHEGADA = [0]


def _na_ordem_da_chegada(vistos: dict[tuple[str, str], dict[str, Any]],
                         buscas: dict[str, object]) -> list[dict[str, Any]]:
    """As linhas de ``vistos`` na ordem em que cada adaptador as viu chegar."""
    for onde in set(_CHEGADAS) | {onde for onde, _ in vistos} | set(buscas):
        guardada = _CHEGADAS.get(onde)
        if guardada is None or guardada[0] != buscas.get(onde):
            _CHEGADAS[onde] = (buscas.get(onde), {})
    for onde, (_busca, ordem) in list(_CHEGADAS.items()):
        for quem in [q for q in ordem if (onde, q) not in vistos]:
            del ordem[quem]
        if not ordem and onde not in buscas and not any(o == onde for o, _ in vistos):
            del _CHEGADAS[onde]
    novos = sorted((par for par in vistos if par[1] not in _CHEGADAS[par[0]][1]),
                   key=lambda par: -(vistos[par]["forca"] or -999))
    for onde, quem in novos:
        _NUMERO_DA_CHEGADA[0] += 1
        _CHEGADAS[onde][1][quem] = _NUMERO_DA_CHEGADA[0]
    return sorted(vistos.values(),
                  key=lambda a: _CHEGADAS[a["adaptador"]][1][str(a["id"])])


def _perto(aparelhos_bz: tuple[Any, ...], adaptadores_bz: tuple[Any, ...],
           ja: list[dict[str, Any]],
           buscas: dict[str, object] | None = None) -> list[dict[str, Any]]:
    """O que CADA rádio está vendo e não está ligado — as listas do «Conectar».

    UMA LINHA POR ADAPTADOR QUE VIU O APARELHO, com o sinal medido POR ELE
    (D-3009-A-LISTA-E-DO-ADAPTADOR-ACESO, 30/09/2026, a
    validar pelo usuário). A lista de antes era de todo aparelho com sinal em qualquer
    adaptador, pelo endereço só: o mesmo aparelho visto por dois ficava com o
    sinal do último que o BlueZ listou, e o «Parear» mandava o chip aceso como
    destino de um aparelho que ele talvez nunca tivesse visto. O painel desenha
    só as do adaptador do chip aceso (:func:`_moldes_de_painel`).

    ``buscas`` é ``{adaptador: quem busca ali}`` — a identidade da busca do
    Hefesto em cada adaptador; quando ela muda, a ordem daquele adaptador
    recomeça (:func:`_na_ordem_da_chegada`).

    QUEM É CONTROLE, E O NOME DA LINHA (O-PAREAR-ESPERA-O-CLIQUE-01): o tipo
    pergunta à classe, ao ``Icon`` e só então ao ``Modalias``
    (:func:`_e_controle_do_bluez`, o mesmo dono da central) — antes de parear,
    o BlueZ não tem o ``Modalias`` do DualSense, e a linha dele caía no
    desenho genérico. O nome é o que ela deu ou o que o aparelho anuncia
    (:func:`_nomes_por_endereco`); sem ele, «DualSense» ou a palavra do tipo.
    Nunca o endereço.
    """
    ligados = {_so_hex(a["id"]) for a in ja}
    adaptador_de = {str(getattr(a, "caminho", "")): _mac(a.endereco) for a in adaptadores_bz}
    nomes = _nomes_por_endereco(aparelhos_bz)
    vistos: dict[tuple[str, str], dict[str, Any]] = {}
    for a in aparelhos_bz:
        onde = adaptador_de.get(str(a.adaptador), "")
        if not onde or a.conectado or a.rssi is None or _so_hex(a.endereco) in ligados:
            continue
        tipo = ("controle" if _e_controle_do_bluez(a)
                else _tipo_do_aparelho(getattr(a, "icone", ""), a.classe,
                                       getattr(a, "aparencia", None)))
        vistos[(onde, _mac(a.endereco))] = {
            "id": _mac(a.endereco), "adaptador": onde,
            "nome": nomes.get(_mac(a.endereco)) or (
                "DualSense" if tipo == "controle"
                else PALAVRA_DO_TIPO.get(tipo, "aparelho").capitalize()),
            "tipo": tipo, "forca": a.rssi, "conhecido": bool(a.pareado),
        }
    return _na_ordem_da_chegada(vistos, dict(buscas or {}))


def _destino_do_conectar(cena: dict[str, Any]) -> str:
    """O destino do «Conectar»: o adaptador ABERTO na lista, e nenhum outro."""
    if not cena["lugares"]:
        return ""
    ids = {lug["id"] for lug in cena["lugares"]}
    if cena.get("aberto") in ids:
        return str(cena["aberto"])
    return str(cena.get("destino_da_central") or cena["lugares"][0]["id"])


def _destino_da_central(cena: dict[str, Any], st: dict[str, Any]) -> str:
    """A D8 (`plano_de_radio.ordem_dos_destinos`): o destino quando nenhum"""
    if not cena["lugares"]:
        return ""
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


_CENA_NA_TELA: dict[str, Any] = {}
_ABERTO: dict[str, Any] = {}


def _abrir_na_tela(lid: str | None) -> None:
    """Abre ``lid`` (ou fecha todos, com ``None``) e move o destino junto, na"""
    _ABERTO["lugar"] = lid
    _CENA_NA_TELA["aberto"] = lid
    _CENA_NA_TELA["destino_do_conectar"] = lid or _CENA_NA_TELA.get("destino_da_central", "")


def _laco() -> Any:
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import entrada_a_entrada

    return entrada_a_entrada.o_laco()


def _campos_da_cerimonia() -> dict[str, Any]:
    """As três telas do «Mapear Entrada a Entrada», pelo laço (ENTRADA-A-ENTRADA-02)."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
    from hefesto_dualsense4unix.interface import calibracao_das_entradas as calib

    # `/sys`, e com ela encaixando o DualSense o kernel o segura por segundos.
    foto = _laco().foto_sem_esperar()
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
    nada = _monta().NADA_A_DIZER
    return {"entrada-tela": foto.get("tela") or "", "entrada-contador": contador or nada,
            "entrada-quem": quem or nada}


def campos_do_radio(ctx: Contexto) -> dict[str, Any]:
    """Os campos da seção Rádio e Adaptadores, pela cena da máquina do usuário."""
    global _CENA_NA_TELA
    cena = cena_do_radio(ctx)
    _CENA_NA_TELA = cena
    campos = campos_da_secao(cena, segurar=True)
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


@gesto("08-conexoes.html", "abrir-adaptador")
def abrir_adaptador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Abre um adaptador e fecha os outros (acordeão exclusivo, ordem de produto)."""
    lug = _lugar_na_tela(o)
    if len(_CENA_NA_TELA.get("lugares") or ()) == 1:
        return {"armou": True}
    _abrir_na_tela(None if _CENA_NA_TELA.get("aberto") == lug["id"] else lug["id"])
    return {"armou": True}


@gesto("08-conexoes.html", "adaptador-reordenar", grava="guardar_ordem_dos_adaptadores")
def adaptador_reordenar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A ordem das caixas que ela arrastou — gravada, e a sala nasce nela.

    Decisão, 25/09/2026. O roteiro da página solta a caixa no lugar e
    manda a ordem NOVA, de cima para baixo, pelos ``data-id`` das caixas (o
    endereço de cada adaptador), e ela vai para o adaptador, pelo endereço —
    o mesmo dono do nome dele (``utils/maquina.guardar_ordem_dos_adaptadores``,
    desde 28/09/2026; antes ia para o ``gui_prefs``, pelo lugar, e a lista de
    lá sai aqui). Um id que não está na tela recusa: a ordem nunca inventa um
    adaptador. <!-- noqa-acento: citação literal -->
    """
    ids = str(o.get("valor") or "").split()
    na_tela = {str(lug["id"]): lug for lug in _CENA_NA_TELA.get("lugares") or ()}
    if not ids or any(i not in na_tela for i in ids):
        raise ValueError(f"a ordem não disse os adaptadores da tela ({ids!r})")
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.gui_prefs import esquecer_a_ordem_dos_adaptadores_de_antes
    from hefesto_dualsense4unix.utils.maquina import guardar_ordem_dos_adaptadores

    if not guardar_ordem_dos_adaptadores(ids):
        raise RuntimeError("a ordem das caixas não foi gravada")
    esquecer_a_ordem_dos_adaptadores_de_antes()
    _esquecer("maquina")
    _CENA_NA_TELA["lugares"] = [na_tela[i] for i in ids] + [
        lug for i, lug in na_tela.items() if i not in ids]


def _gravar_o_nome(endereco: str, nome: str) -> Any:
    """O nome é do ADAPTADOR, pelo endereço, e mora no `maquina.json`; o `Alias`"""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.entrada_a_entrada import dar_nome_ao_adaptador

    feito = dar_nome_ao_adaptador(endereco, nome)
    _esquecer("maquina")
    _reler_a_declaracao()
    return feito


def _so_o_foco(o: dict[str, Any]) -> bool:
    """O clique que só POSICIONA o cursor num campo de nome: o ouvinte do piloto"""
    return str(o.get("evento") or "") == "click"


@gesto("08-conexoes.html", GESTO_DO_APELIDO, grava="dar_nome_ao_adaptador")
def adaptador_renomear(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O nome que ela dá ao adaptador — dele, pelo endereço, e vai com ele."""
    if _so_o_foco(o):
        return {"armou": True}
    lug = _lugar_na_tela(o)
    novo = nome_dado(str(o.get("valor") or ""))
    if novo == str(lug.get("nome") or ""):
        return None
    feito = _gravar_o_nome(str(lug["id"]), novo)
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
    <!-- noqa-acento: citação literal -->
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
    if ap.get("tipo") == "controle":
        novo = nome_dado(novo)
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
    return _pedir_ao_radio(p, aparelho, destino)


def _pedir_ao_radio(p: Any, aparelho: str | None, destino: str) -> dict[str, Any]:
    """O pedido do `radio.mover`, sem a trava da tela: a resposta é da central."""
    parametros: dict[str, Any] = {"destino": destino}
    if aparelho:
        parametros["aparelho"] = aparelho
    resposta = p.resultado("radio.mover", **parametros)
    status = str((resposta or {}).get("status") or "") if isinstance(resposta, dict) else ""
    if status != "ok":
        raise RuntimeError(f"o rádio não aceitou agora ({status or 'sem resposta'})")
    return {"armou": True}


@gesto("08-conexoes.html", "confirmar-mudanca", grava="radio.mover")
def confirmar_mudanca(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Mover» (e «Mover e ligar»): o aparelho vai para o destino da pergunta."""
    alvo, destino = str(o.get("alvo") or ""), str(o.get("destino") or "")
    if not alvo or not destino:
        raise ValueError("a pergunta não disse quem vai nem para onde")
    feito = _mover(p, alvo, destino)
    _abrir_na_tela(destino)
    return feito


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
    """«Conectar»: sem alvo, SÓ ABRE o painel com a lista — quem liga a busca"""
    alvo = str(o.get("alvo") or "")
    if not alvo:
        return _so_abre()
    escolha = _escolher_na_busca(p, alvo)
    if escolha is not None:
        return escolha
    destino = str(_CENA_NA_TELA.get("destino_do_conectar") or "")
    if not destino:
        raise RuntimeError("não há adaptador Bluetooth para conectar")
    feito = _mover(p, alvo, destino)
    _abrir_na_tela(destino)
    return feito


def _escolher_na_busca(p: Any, alvo: str) -> dict[str, Any] | None:
    """O clique do usuário numa linha do «Conectar» com a busca de pé: a ESCOLHA."""
    busca = _onde_espera(_CENA_NA_TELA.get("lugares") or [], _CENA_NA_TELA.get("aparelhos") or [])
    if not busca:
        return None
    feito = _pedir_ao_radio(p, alvo, busca)
    _abrir_na_tela(busca)
    return feito


@gesto("08-conexoes.html", "parear-aparelho", grava="radio.mover")
def parear_aparelho(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Parear» um aparelho que o rádio achou: com a busca de pé, a escolha"""
    alvo = str(o.get("alvo") or "")
    if not alvo:
        raise ValueError("o clique não disse qual aparelho")
    escolha = _escolher_na_busca(p, alvo)
    if escolha is not None:
        return escolha
    return _mover(p, alvo, str(_CENA_NA_TELA.get("destino_do_conectar") or ""))


@gesto("08-conexoes.html", "escolher-adaptador", grava="radio.mover")
def escolher_adaptador(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O chip do «Conectar»: ABRE o adaptador escolhido, que é o destino."""
    lug = _lugar_na_tela(o)
    lid = str(lug["id"])
    busca = _onde_espera(_CENA_NA_TELA.get("lugares") or [], _CENA_NA_TELA.get("aparelhos") or [])
    if busca and busca != lid:
        feito = _pedir_ao_radio(p, None, lid)
        _abrir_na_tela(lid)
        return feito
    _abrir_na_tela(lid)
    return {"armou": True}


def _linha_na_tela(o: dict[str, Any]) -> dict[str, Any]:
    """A linha do clique pelo par ``(alvo, lugar)``: o mesmo controle desligado"""
    alvo = str(o.get("alvo") or "")
    lugar = str(o.get("lugar") or o.get("destino") or "")
    ap = next((a for a in _CENA_NA_TELA.get("aparelhos", ())
               if a["id"] == alvo and (not lugar or a.get("lugar") == lugar)), None)
    if not isinstance(ap, dict):
        raise ValueError(f"o clique não disse uma linha que está na tela ({alvo!r}, {lugar!r})")
    return ap


@gesto("08-conexoes.html", "tentar-de-novo", grava="radio.mover")
def tentar_de_novo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Tentar de Novo»: o mesmo «Conectar», no MESMO adaptador da linha — e em"""
    lug = _lugar_na_tela(o)
    lid = str(lug["id"])
    linhas = [ap for ap in _CENA_NA_TELA.get("aparelhos", ())
              if ap.get("nao_conectou") and ap.get("lugar") == lid]
    pedida = str(o.get("linha") or "")
    linha = next((ap for ap in linhas if ap["id"] == pedida), linhas[0] if linhas else None)
    outro = (str(linha.get("aparelho") or "")
             if linha is not None and linha.get("tipo") != "controle" else "")
    feito = _mover(p, outro, lid) if outro else _ligar_a_busca(p, True, lid)
    if linha is not None and not outro:
        with contextlib.suppress(Exception):
            _tirar_a_linha(p, linha)
    _abrir_na_tela(lid)
    return feito


@gesto("08-conexoes.html", "parear-de-novo", grava="esquecer_o_pareamento")
def parear_de_novo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Parear de Novo»: o controle que o BlueZ ainda tem pareado aqui e não conectou
    (a chave dele foi apagada, ele está em modo de parear): o pareamento velho sai
    e a busca abre neste adaptador, onde ele chega como novo."""
    lug = _lugar_na_tela(o)
    lid = str(lug["id"])
    linhas = [ap for ap in _CENA_NA_TELA.get("aparelhos", ())
              if ap.get("nao_conectou") and ap.get("pareado_aqui") and ap.get("lugar") == lid]
    pedida = str(o.get("linha") or "")
    linha = next((ap for ap in linhas if ap["id"] == pedida), None)
    if linha is None:
        raise ValueError("esta linha não tem um pareamento velho para refazer")
    if _CENA_NA_TELA.get("ocupado"):
        raise RuntimeError(_por_que_o_radio_esta_ocupado())
    feito = _esquecer_o_pareamento(lid, str(linha["aparelho"]))
    if not getattr(feito, "deu", False):
        raise RuntimeError(str(getattr(feito, "porque", "") or "o Bluetooth não esqueceu"))
    _esquecer("bluez")
    with contextlib.suppress(Exception):
        _tirar_a_linha(p, linha)
    _ligar_a_busca(p, True, lid)
    # O mesmo clique é a escolha do usuário: a central pareia ESTE endereço quando a janela o
    # ver. Se ela não aceitar agora, a busca segue aberta e o «Parear» da lista fecha.
    with contextlib.suppress(Exception):
        _pedir_ao_radio(p, str(linha["aparelho"]), lid)
    _abrir_na_tela(lid)
    return {"armou": True}


@gesto("08-conexoes.html", "parear-o-pedido", grava="radio.mover")
def parear_o_pedido(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O «Parear» do cartão do controle que pede para parear: o mesmo ``radio.mover`` do
    «Mover», no adaptador que o ouve — a central tira o par velho do destino, espera o
    controle (ele já está em modo de parear), pareia, confere e esquece a origem."""
    alvo, destino = _mac(o.get("alvo")), _mac(o.get("destino"))
    pedido = next((x for x in _CENA_NA_TELA.get("pedindo") or ()
                   if x.get("aparelho") == alvo and x.get("lugar") == destino), None)
    if pedido is None:
        raise ValueError("este controle não está mais pedindo para parear aqui")
    feito = _mover(p, _com_dois_pontos(alvo), destino)
    _abrir_na_tela(destino)
    return feito


def _tirar_a_linha(p: Any, ap: dict[str, Any]) -> dict[str, Any]:
    """A linha «Não Conectou» sai — na CENTRAL (``radio.dispensar``,"""
    if not ap.get("aparelho"):
        _DISPENSADOS.add(str(ap.get("chave") or ""))
        return {"armou": True}
    resposta = p.resultado("radio.dispensar", aparelho=_com_dois_pontos(ap["aparelho"]))
    if not isinstance(resposta, dict) or resposta.get("status") != "ok":
        status = resposta.get("status") if isinstance(resposta, dict) else ""
        raise RuntimeError(f"a linha não saiu agora ({status or 'sem resposta'})")
    return {"armou": True}


@gesto("08-conexoes.html", "dispensar-linha", grava="radio.dispensar")
def dispensar_linha(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O X da linha «Não Conectou»: tira a linha, e só ela — não esquece nada"""
    ap = _linha_na_tela(o)
    if not _tem_x(ap):
        raise ValueError("só a linha «Não Conectou» tem o X")
    return _tirar_a_linha(p, ap)


def _o_adaptador_foi_descrito(ap: dict[str, Any]) -> bool:
    """O menu do «⋮» só nasce no adaptador que o BlueZ já descreveu (``sabido``,"""
    lug = next((lug for lug in _CENA_NA_TELA.get("lugares", ())
                if str(lug.get("id")) == str(ap.get("lugar"))), None)
    return lug is not None and bool(lug.get("sabido", True))


@gesto("08-conexoes.html", "aparelho-menu")
def aparelho_menu(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O «⋮» da linha: a página abre o menu (o «Esquecer»), e nada muda aqui."""
    ap = _linha_na_tela(o)
    if not _tem_menu(ap):
        raise ValueError("esta linha não tem menu")
    if _pode_esquecer(ap) and not _o_adaptador_foi_descrito(ap):
        raise RuntimeError("esperando o Bluetooth do sistema descrever o adaptador")
    return _so_abre()


@gesto("08-conexoes.html", "esquecer-aparelho")
def esquecer_aparelho(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O «Esquecer» do menu «⋮»: a página abre a pergunta, e nada sai do rádio"""
    ap = _linha_na_tela(o)
    if not _pode_esquecer(ap):
        raise ValueError("esta linha não tem o que esquecer")
    return _so_abre()


def _por_que_o_radio_esta_ocupado() -> str:
    """A razão de a escrita no BlueZ esperar: a busca ligada, ou um controle que chega."""
    if _CENA_NA_TELA.get("procurando") == PROCURAR_LIGADO:
        return DESLIGUE_O_PROCURAR
    return "esperando um controle chegar"


@gesto("08-conexoes.html", "confirmar-esquecer", grava="esquecer_o_pareamento")
def confirmar_esquecer(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Esquecer» da pergunta do «⋮»: o pareamento DESTE aparelho NESTE adaptador"""
    ap = _linha_na_tela(o)
    if not _pode_esquecer(ap):
        raise ValueError("esta linha não tem o que esquecer")
    if _CENA_NA_TELA.get("ocupado"):
        raise RuntimeError(_por_que_o_radio_esta_ocupado())
    aparelho = str(ap.get("aparelho") or ap["id"])
    feito = _esquecer_o_pareamento(str(ap["lugar"]), aparelho)
    if not getattr(feito, "deu", False):
        raise RuntimeError(str(getattr(feito, "porque", "") or "o Bluetooth não esqueceu"))
    _esquecer("bluez")


@gesto("08-conexoes.html", "equilibrar-radio")
def equilibrar_radio(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Equilibrar»: a proposta da central abre a pergunta; sem proposta, treme (R8)."""
    if _CENA_NA_TELA.get("ocupado"):
        raise RuntimeError("esperando um controle chegar")
    if not _CENA_NA_TELA.get("proposta"):
        raise RuntimeError("já está equilibrado")
    return {"armou": True}


def _ligar_a_busca(p: Any, ligada: bool, destino: str) -> dict[str, Any]:
    """O ``radio.busca.set`` com valor absoluto, e o verde só com a resposta"""
    parametros: dict[str, Any] = {"ligada": ligada}
    if destino:
        parametros["destino"] = destino
    resposta = p.resultado("radio.busca.set", **parametros)
    busca = resposta.get("busca") if isinstance(resposta, dict) else None
    status = str(resposta.get("status") or "") if isinstance(resposta, dict) else ""
    feita = (isinstance(busca, dict) and (not destino or _mac(busca.get("adaptador"))
                                          == _mac(destino))) if ligada else busca is None
    if status != "ok" or not feita:
        raise RuntimeError(f"{PROCURAR_RECUSA} ({status or 'sem resposta'})")
    return {"armou": True}


@gesto("08-conexoes.html", "radio-procurar", grava="radio.busca.set")
def radio_procurar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O «Procurar»: liga e desliga a busca do rádio (O-CONECTAR-E-UM-INTERRUPTOR-01)."""
    if str(o.get("evento") or "click") != "click":
        return None
    agora = str(_CENA_NA_TELA.get("procurando") or TRAVESSAO_DO_PROCURAR)
    if agora not in (PROCURAR_LIGADO, PROCURAR_DESLIGADO):
        raise RuntimeError(PROCURAR_RECUSA)
    ligar = agora != PROCURAR_LIGADO
    destino = str(_CENA_NA_TELA.get("destino_do_conectar") or "") if ligar else ""
    if ligar and not destino:
        raise RuntimeError("não há adaptador Bluetooth para procurar")
    feito = _ligar_a_busca(p, ligar, destino)
    if ligar:
        _abrir_na_tela(destino)
    return feito


def _so_abre() -> dict[str, Any]:
    """Os gestos que só ABREM o que já veio pintado: a página abre, o Python"""
    return {"armou": True}


@gesto("08-conexoes.html", "cancelar-mudanca")
def cancelar_mudanca(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Cancelar» a pergunta: nada muda no rádio."""
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
    """O microfone de um controle: o MESMO ato do 🎙 da aba Controles (D-12)."""
    uniq = str(o.get("alvo") or "")
    if not uniq or not ctx.por_uniq(uniq):
        raise ValueError("o clique não disse em qual controle")
    _o_mudo_da_aba_02(ctx, {"uniq": uniq, "mudo": "microfone"}, p)


@gesto("08-conexoes.html", "entrada-comecar")
def entrada_comecar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Abrir a âncora começa o laço — no lugar do «Onde fica?», se veio de um."""
    _laco().comecar(str(o.get("alvo") or "") or None)
    return {"armou": True}


@gesto("08-conexoes.html", "entrada-face", grava="responder")
def entrada_face(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A resposta de produto — uma das quatro faces do produto —, gravada na hora."""
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
METODOS = {"controller.target.set", "radio.mover", "radio.ponte.ligar_aqui",
           "radio.busca.set", "radio.dispensar"}


PAGINA = "08-conexoes.html"
PISO_DA_ABA = 49
PROVAS = [
    # e o `_indice` cai na posição quando o daemon não publicou `index`.
    {"pagina": PAGINA, "gesto": "alvo", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["controller.target.set"], {"index": 0})]},
    {"pagina": PAGINA, "gesto": "todos", "clique": {"uniq": "", "controle": ""},  # (noqa-acento) id
     "chama": [("chamar", ["controller.target.set"], {"index": None})]},
    {"pagina": PAGINA, "gesto": "sala-altura", "clique": {"modo": "acima"},  # (noqa-acento) id
     "chama": [("machine_declare", [{"mesa": {"altura_da_antena": "acima"}}], {})]},
    {"pagina": PAGINA, "gesto": "sala-visada", "clique": {"modo": ""},  # (noqa-acento) id
     "chama": [("machine_declare", [{"mesa": {"linha_de_visada": None}}], {})]},
    {"pagina": PAGINA, "gesto": "mic-existe", "clique": {"valor": "Ligado"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": True}}}], {})]},
    {"pagina": PAGINA, "gesto": "mic-existe", "clique": {"valor": "Desligado"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": False}}}], {})]},
]

_NO_MAQUINA = "grava no `maquina.json`; o `state_full` não o republica"
_NO_BLUEZ = "grava o `Alias` no BlueZ; o `state_full` não o publica"
_O_MAPA = "grava o desenho do gabinete (`_gravar_o_mapa`); o `state_full` não publica o mapa"

#: Cada gesto sem eco no `state_full`, e a razão: sem ela a declaração é lápide.
RAZAO_DO_SEM_ECO: dict[str, str] = {
    "sala-altura": _NO_MAQUINA,
    "sala-visada": _NO_MAQUINA,
    "mic-existe": "grava no `maquina.json` e sobe ou desce o `bt_mic` no mesmo pedido: "
                  "tem efeito vivo, não tem eco",
    "vizinho-o-que-e": _NO_MAQUINA,
    "receptor-descobrir": "guarda o passo na tela; a banda achada vai ao `maquina.json` no tique "
                          "que fecha a medida, e o `state_full` não a republica",
    "ignorar": "a dispensa de uma ordem vai ao `maquina.json`; o `state_full` não a publica",
    "examinar-portas": "não toca o daemon: muda a tira do Check-up no tique seguinte",
    "teto-da-vibracao": "grava no perfil; o efeito vivo vem do `profile.switch`, e o "
                        "`state_full` não publica override por controle",
    "escolher-aparelho": "primeiro tempo do gesto de dois: guarda o aparelho na mão e "
                         "não chama a ponte",
    "escolher-entrada": _O_MAPA,
    "tirar-daqui": _O_MAPA,
    "nova-entrada": _O_MAPA,
    "nova-extensao": _O_MAPA,
    "nova-face": _O_MAPA,
    "adaptador-renomear": _NO_MAQUINA,
    "aparelho-renomear": _NO_BLUEZ,
    "entrada-face": _NO_MAQUINA,
    "entrada-nao-alcanco": _NO_MAQUINA,
    "adaptador-reordenar": "grava a ordem das caixas no `gui_preferences.json`, "
                           "que o daemon não lê",
    "dono-renomear": _NO_BLUEZ,
    "perfil-do-controle": "grava a economia de cada controle no `maquina.json`; o "
                          "`state_full` não a publica",
    "mapear-gravar": "grava a porta da vez no `maquina.json` pelo dono do mapa",
    "mapear-comecar": "só liga o olhar do dono, no processo da interface",
    "mapear-parar": "só desliga o olhar do dono, no processo da interface",
    "esquecer-aparelho": "só abre a pergunta, ou tira a linha do «Não Conectou»",
    "confirmar-esquecer": "apaga a chave do pareamento no BlueZ, que o `state_full` "
                          "não publica",
}
SEM_ECO = tuple(RAZAO_DO_SEM_ECO)


# só leitura, com o ✓ de «tudo certo». <!-- noqa-acento: citação literal -->
CERTO = "✓"
#: `native_mode` é do daemon (o jogo lê o DualSense de verdade); fora dele, o
MODO_NATIVO = "Nativo"
MODO_PELO_HEFESTO = "Pelo Hefesto"


def selo_do_estado(rotulo: str, valor: str = "", estado: str = "ok") -> str:
    """Um selo da linha: «Mic ✓», «Bateria 64% · carregando», «Visto como Xbox 360»."""
    miolo = html.escape(rotulo)
    if valor:
        miolo += f" <b>{html.escape(valor)}</b>"
    if estado == "ok":
        miolo += f' <i class="certo">{CERTO}</i>'
    classe = f"est {estado}" if estado else "est"
    return f'<span class="{classe}">{miolo}</span>'


def modo_da_fileira(st: dict[str, Any]) -> str:
    """O «Modo de conexão» da linha: o nome do chip aceso na aba Jogar.

    O pedido diz *«Modo de conexão (DualSense)»*: é o modo que ela escolhe
    na fileira da Jogar, e não a posição do interruptor. Quem decide qual chip
    acende é o dono da Jogar (`a01_jogar._estado_da_tela`), e o nome do chip é
    o da tabela da fileira (`painel.CHIPS_DA_ESCADA`) — nada digitado aqui. Com
    o Hefesto desligado a palavra é a do interruptor (``Nativo``); sem leitura,
    a de antes (``Pelo Hefesto``), que é verdade enquanto o daemon responde.
    """
    if st.get("native_mode"):
        return MODO_NATIVO
    try:
        from hefesto_dualsense4unix.app.actions.jogar import painel

        from . import a01_jogar

        tela = a01_jogar._estado_da_tela(st)
        chave = (a01_jogar.CHIP_DO_STEAM_INPUT if tela.get("steam-input-aceso")
                 else str(tela.get("modo-aceso") or ""))
        for chip in painel.CHIPS_DA_ESCADA:
            if chip.chave == chave:
                return str(chip.rotulo)
    except Exception:
        pass
    return MODO_PELO_HEFESTO


# D-O-ESCOPO-DO-MIC-SAIU-DA-08 — 25/09/2026, pedido (A-08-O-CHECKUP-ABSORVE-
def estado_do_controle(c: dict[str, Any], eu: dict[str, Any], st: dict[str, Any],
                       declaracao: Any, modo: str | None = None) -> dict[str, str]:
    """Os seis selos de UM controle, lidos do daemon vivo e da declaração.

    `c` é a entrada do `state_full` (o `ctx.conectados`), `eu` a da mesa (o
    número e a máscara por aparelho), `st` o estado inteiro. Vale para todo
    transporte e todo modo: nenhum ramo pergunta qual é o controle nem quantos
    há na mesa.
    """
    uniq = str(c.get("uniq") or "")
    via = str(c.get("transport") or "").lower()
    audio_lido = c.get("audio")
    audio: dict[str, Any] = audio_lido if isinstance(audio_lido, dict) else {}

    if not _mic_declarado(declaracao, uniq):
        mic = selo_do_estado("Mic", "desligado")
    elif audio.get("mic_mudo") is True:
        mic = selo_do_estado("Mic", "mudo")
    elif via == "bt" and uniq not in (st.get("pontes_confirmadas") or {}) \
            and not c.get("hz_voz"):
        mic = selo_do_estado("Mic", "sem ponte", "warn")
    else:
        mic = selo_do_estado("Mic")

    fala = c.get("speaker") if isinstance(c.get("speaker"), dict) else None
    if fala is None:
        som = selo_do_estado("Som", TRAVESSAO_DA_LINHA, "")
    elif fala.get("muted"):
        som = selo_do_estado("Som", "mudo")
    else:
        som = selo_do_estado("Som")

    modo_da_linha = selo_do_estado("Modo de conexão",
                                   modo if modo is not None else modo_da_fileira(st), "")
    visto = selo_do_estado("Visto como", str(eu.get("mascara") or TRAVESSAO_DA_LINHA), "")

    # (:func:`nome_com_a_bateria`); a queda do rádio aparece no exame e em
    # Rádio e Adaptadores. (noqa-acento: citação literal)
    return {"est-mic": mic, "est-som": som, "est-modo": modo_da_linha, "est-visto": visto}


def nome_com_a_bateria(rotulo: str, pct: object) -> str:
    """«Cosmic Red • BT • 85%» — o rótulo curto e a carga, quando ela é lida."""
    bateria = _texto_da_bateria(pct)
    if not rotulo or not bateria or bateria == TRAVESSAO_DA_LINHA:
        return rotulo
    return f"{rotulo}{_PONTO}{html.escape(bateria)}"


TRAVESSAO_DA_LINHA = "—"


def economia_do_controle(declaracao: Any, uniq: str) -> tuple[bool | None, str | None]:
    """``(a escolha deste controle, o teto da mesa)``, lidos da declaração."""
    try:
        declarado = (declaracao.controles or {}).get(_so_hex(uniq))
        escolha = getattr(declarado, "economia", None)
    except Exception:
        escolha = None
    teto = getattr(getattr(declaracao, "orcamento", None), "teto", None)
    return escolha, (teto if isinstance(teto, str) else None)


def perfil_na_linha(declaracao: Any, uniq: str) -> dict[str, str]:
    """O botão aceso do Perfil de Desempenho do cartão (endereço `perfil`)."""
    from hefesto_dualsense4unix.app.actions.config import secao_orcamento

    escolha, teto = economia_do_controle(declaracao, uniq)
    return {"perfil": secao_orcamento.perfil_do_controle(teto, escolha)}


def _recusa_da_mesa() -> str:
    """Por que um cartão não sai da «Bateria Longa» global (vai ao diário)."""
    from hefesto_dualsense4unix.app.actions.config import secao_orcamento as orc

    longa = orc.ROTULOS_DOS_PERFIS[orc.PERFIL_BATERIA_LONGA]
    return (f"A «{longa}» da aba Sistema vale para todos os controles; para mudar "
            "um só, escolha outro Perfil Global de Bateria lá.")


def _nomes_dos_donos() -> dict[str, str]:
    """``{endereço: nome}`` pelo dono do nome (o ``Alias`` do BlueZ)."""
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
    """O nome do jogador dono do controle — pelo dono do nome (o `Alias`)."""
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("dono-renomear: o clique não disse em qual controle")
    novo = nome_dado(str(o.get("valor") or ""))
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


@gesto("08-conexoes.html", "perfil-do-controle", grava="machine_declare")
def perfil_do_controle_gesto(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Os três botões do Perfil de Desempenho de UM controle."""
    from hefesto_dualsense4unix.app.actions.config import secao_orcamento as orc
    from hefesto_dualsense4unix.profiles import schema

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("perfil-do-controle: o clique não disse em qual controle")
    escolhido = str(o.get("valor") or o.get("v") or "")
    if escolhido not in orc.PERFIS:
        raise ValueError(f"perfil-do-controle: {escolhido!r} não é um dos três perfis")
    escolha, teto = economia_do_controle(_declaracao(), uniq)
    if schema.origem_da_economia(escolha, schema.mesa_em_economia(teto)) == "mesa":
        if escolhido == orc.PERFIL_BATERIA_LONGA:
            return
        raise RuntimeError(_recusa_da_mesa())
    if orc.ECONOMIA_POR_PERFIL[escolhido] is escolha:
        return
    ok, motivo = _resposta(p.machine_declare(orc.declaracao_do_perfil(uniq, escolhido)))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o que você declarou")
    _reler_a_declaracao()


# é o estado, e o tique a pinta. <!-- noqa-acento: citação literal -->
MAPEAR_DIZ = {
    "parado": "Conecte o DualSense por USB numa entrada do computador.",
    "esperando": "Conecte o DualSense por USB numa entrada do computador.",
    "porta": ("Conecte um DualSense em cada entrada USB do seu dispositivo. Nomeie a "
              "entrada (ou deixe vazia para ela ser enumerada). Ao final, valide e, "
              "caso necessário, faça os ajustes na entrada no botão Mapa das Conexões."),
    "procurando": "Procurando…",
}


def _o_mapa() -> Any:
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee

    return ee.o_mapa()


def _ler_o_censo_agora() -> Any:
    """`ler_o_barramento`, guardado em `_CENSO` quando responde. BLOQUEIA:"""
    global _CENSO
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations.censo_do_barramento import (
            ler_o_barramento,
        )

        _CENSO = ler_o_barramento()
    except Exception:
        return None
    return _CENSO


def html_da_porta_medida(porta: dict[str, Any] | None) -> str:
    """O que o Hefesto mediu da porta da vez, em pares «o quê · valor»."""
    if not porta:
        return '<i class="nada"></i>'
    fatos = [("Entrada", str(porta.get("rotulo") or ""))]
    if porta.get("usb"):
        fatos.append(("Velocidade", f"USB {porta['usb']}"))
    fatos.append(("Ligação", f"Num hub ({porta.get('hub_produto') or 'hub'})"
                  if porta.get("hub") else "Direto no computador"))
    storm = porta.get("storm")
    if isinstance(storm, int) and not isinstance(storm, bool):
        fatos.append(("Quedas", "Nenhuma em 7 dias" if storm == 0
                      else f"{storm} {'queda' if storm == 1 else 'quedas'} em 7 dias"))
    if porta.get("lugar_no_gabinete"):
        fatos.append(("Onde fica", str(porta["lugar_no_gabinete"])))
    pares = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in fatos if v)
    return f'<dl class="mp-fatos">{pares}</dl>'


def _mapeadas(portas: Any) -> list[dict[str, Any]]:
    """As entradas do mapa que já têm número, na ordem do dono (`ler_o_mapa`:"""
    return [p for p in (portas or []) if isinstance(p, dict) and p.get("numero")]


def html_das_entradas_mapeadas(portas: Any) -> str:
    """As entradas já mapeadas, uma por linha: o nome e onde ela fica."""
    mapeadas = _mapeadas(portas)
    if not mapeadas:
        return '<li class="vazio">Nenhuma ainda.</li>'
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.entrada_a_entrada import rotulo_do_numero

    linhas = []
    for porta in mapeadas:
        numero = str(porta["numero"])
        entrada = rotulo_do_numero(numero) or ""
        face = str(porta.get("lugar_no_gabinete") or "")
        nome = str(porta.get("nome") or "")
        if nome:
            titulo, onde = nome, " · ".join(x for x in (entrada, face) if x)
        else:
            titulo, onde = entrada, face
        linhas.append(f"<li><b>{html.escape(titulo)}</b>"
                      f"<span>{html.escape(onde)}</span></li>")
    return "".join(linhas)


def conta_das_mapeadas(portas: Any) -> str:
    """«15 entradas mapeadas.» — a conta da MESMA lista do disco."""
    quantas = len(_mapeadas(portas))
    if not quantas:
        return ""
    return f"{quantas} {'entrada mapeada' if quantas == 1 else 'entradas mapeadas'}."


def campos_do_mapear(foto: dict[str, Any] | None = None) -> dict[str, str]:
    """Os campos da tela do Mapear, a partir da foto do dono."""
    if foto is None:
        try:
            foto = _o_mapa().foto_sem_esperar()
        except Exception:
            foto = {"estado": "parado"}
    procurando = bool(foto.get("procurando"))
    estado = str(foto.get("estado") or "parado")
    portas = foto.get("portas")
    return {
        "mapear-diz": MAPEAR_DIZ.get("procurando" if procurando else estado,
                                     MAPEAR_DIZ["parado"]),
        "mapear-estado": "esperando" if procurando else estado,
        "mapear-porta": html_da_porta_medida(None if procurando else foto.get("porta")),
        "mapear-lista": (_monta().NADA_A_DIZER if procurando and portas is None
                         else html_das_entradas_mapeadas(portas)),
        "mapear-conta": conta_das_mapeadas(portas),
    }


@gesto("08-conexoes.html", "mapear-comecar")
def mapear_comecar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A tela do Mapear abriu: o dono começa a esperar a porta da vez."""
    global _LOGICA
    _LOGICA = None
    _o_mapa().abrir()


@gesto("08-conexoes.html", "mapear-gravar",
       grava="a porta da vez no mapa das portas do maquina.json, pelo dono do mapa")
def mapear_gravar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Salvar esta entrada»: o nome e o lugar da porta da vez, pelo dono."""
    global _LOGICA
    forma_lida = o.get("forma")
    forma: dict[str, Any] = forma_lida if isinstance(forma_lida, dict) else {}
    nome = str(forma.get("nome") or "").strip() or None
    lugar = str(forma.get("lugar") or "").strip() or None
    _o_mapa().gravar(nome=nome, lugar=lugar)
    _LOGICA = None
    _reler_a_declaracao()


@gesto("08-conexoes.html", "mapear-parar")
def mapear_parar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A tela do Mapear fechou: o dono para de olhar as portas."""
    _o_mapa().parar()


def _selo_da_declaracao() -> tuple[int, int, int] | None:
    """`(inode, mtime_ns, tamanho)` do `maquina.json`, ou `None` sem ele."""
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina

        st = caminho_da_maquina().stat()
    except Exception:
        return None
    return (st.st_ino, st.st_mtime_ns, st.st_size)


_SELO_DA_DECLARACAO: tuple[int, int, int] | None = None
