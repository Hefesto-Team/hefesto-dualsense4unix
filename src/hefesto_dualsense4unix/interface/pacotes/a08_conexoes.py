#!/usr/bin/env python3
"""O pacote da aba `08` Conexões.

Tem dono a contagem da mesa por transporte, o que o cabeçalho promete (`2 controles • 1 USB • 1
BT`): sai de `controllers[]`, contando os CONECTADOS. O exame não tem dono no `state_full`: as
linhas do Check-up saem de `integrations/exame_da_mesa`, que lê o sistema por outro caminho,
resultado de um exame que alguém mandou rodar; pintá-las do `state_full` seria inventar.

Esta aba tem três fontes, o que a faz diferente das outras nove:

    state_full          o daemon, a 500 ms — a mesa, o transporte, a bateria
    maquina.json        a DECLARAÇÃO dela — o que barramento nenhum responde
    /sys + busctl       o exame e os rádios vizinhos — lidos SOB DEMANDA

As duas últimas ficam fora do tique de propósito (ver "O QUE SE LÊ DA MÁQUINA, E QUANDO"), o que dá
trabalho ao botão **Examinar Portas** e um sujeito ao ⊘ de cada linha do Check-up.
"""
from __future__ import annotations

import contextlib
import dataclasses as _dataclasses
import html
import re
import select
import sys
import time
from typing import Any

from hefesto_dualsense4unix.app.actions import external_controllers as _marcas
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.interface.monta import dono_na_linha

from . import TODOS_OS_LUGARES, Contexto, em_fundo, nome_do_jogador, perfil, registrar

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
        em_fundo.em_fundo("censo", _ler_o_censo_agora, 0.0)
    return _CENSO


def _logica_do_mapa() -> Any:
    """O rascunho do gabinete DO USUÁRIO — `LogicaDoMapa` sobre o que o usuário declarou."""
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

    Pergunta ao dono: `integrations/censo_do_barramento` classifica pela tripla
    `bInterfaceClass/SubClass/Protocol` e `GRAU_LIDO` declara que a palavra veio do kernel e não de
    um chute. Grau `desconhecido` (classe `ff`, fabricante que declinou) devolve `""` e a pergunta
    segue como a única resposta honesta. Mesmo degrau da janela estável
    (`secao_mesa._celula_do_que_e`).
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

    Pergunta aos dois donos (a lista de rótulos é `_TIPOS_DE_RADIO`, a moldura é a própria
    pergunta), então não envelhece quando a lista ganha uma opção. Digitá-las faria o clique na
    sugestão nova cair no `raise ValueError` do gesto, que nesta aba é recusa **calada**
    (`hefesto_vivo._recusou_dizendo` só leva `RuntimeError` à tela).
    """
    pergunta = _a_pergunta()
    para_id, _ = _tipos_de_radio()
    return frozenset(_pergunta_sugerida(r, pergunta) for r in para_id)


def _mesa_declarada(declaracao: Any) -> dict[str, Any]:
    """As duas respostas que barramento nenhum dá: a altura e a visada.

    Alimentam `exame_da_mesa.vizinhanca_das_portas` e fecham o laço dos gestos `sala-altura` e
    `sala-visada`: o que o usuário declarou muda a linha do Check-up desta MESMA aba.
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

    A GTK mostra isso desde sempre (`secao_mesa._linha_declarada` lê `_mesa_em_vigor()` e
    pré-seleciona o botão gravado ANTES de ligar o sinal). Esta tela não mostrava (medido em
    03/09/2026: o `maquina.json` dizia `altura_da_antena='acima'` e `linha_de_visada='com_gente'` e
    os TRÊS botões da VISADA estavam apagados, com o "Sim" da ALTURA aceso por coincidência do
    mockup, um acerto sem leitura que erra no primeiro clique). Sem eco o segundo clique parece o
    primeiro, e gesto que grava sem dizer é indistinguível de gesto que não fez nada.

    O `None` não acende nada (regra do dono: `secao_mesa` só chama `set_active_id` com `gravado is
    not None`): o produto **não distingue** "nunca respondeu" de "respondeu Não sei", as duas gravam
    `None` (`sala_altura`: `escolha or None`; `secao_mesa._valor_do_seletor` converte igual).
    Acender "Não sei" no `None` poria na boca dela uma resposta que pode não ter dado.
    :data:`_ID_NAO_SEI` existe no DESENHO e nunca é emitido aqui: só tira o terceiro botão do modo
    booleano do `escrever()`.
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

    A regra inverteu em 18/09/2026 (*"todos os controles tem que nascer com tudo mic, giroscopio e
    afins"*): antes só `True` contava; agora só `False` desliga e a ausência LIGA, como o daemon
    (`bt_mic.uniqs_recusados`). Seguem DOIS estados na tela, e o controle sobre o qual ninguém disse
    nada cai para o lado do aparelho (um DualSense tem microfone). Erro de leitura responde `True`:
    com o default invertido, o lado seguro é não calar um microfone por engano.
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

    O daemon grava sob lock e só então responde `{"ok": true}` (`_handle_machine_declare`); reler
    aqui faz a tela mostrar no tique seguinte o que o usuário escolheu, não o padrão do desenho.
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
    # `secao_exame._desenhar_o_que_fazer` a escreve com estas palavras.
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

    D-16: o topo do Check-up só dizia QUANDO foi examinado; saber se havia algo errado exigia ler as
    cinco pílulas, e a segunda ordem de serviço (que não cabe nas cinco) não entrava na leitura.

    Nenhuma frase nem conta nasce aqui. As quatro frases são de `ordens_da_mesa.cabecalho()` (*"a
    chave de estado vem CALCULADA AQUI, num lugar só: um segundo lugar decidindo a cor do topo é
    exatamente como o verde volta a conviver com o vermelho (cicatriz de 6fffd547)"*). As duas
    contagens são de `secao_exame.contagens_do_cabecalho`, SEPARADAS de propósito: *"conferi 5
    coisas"* e *"5 coisas não deram resposta"* são afirmações opostas, e a tela que as colapsa mente
    de verde.

    Duas perguntas respondem sobre esta linha e nenhuma vê a outra; `secao_exame.o_mais_grave` as
    concilia: `exame_da_mesa.veredito()` lê as linhas e conhece `problema`, `cabecalho()` lê ordens
    e contagens e **não** conhece. Escalar não inventa estado (é sempre um dos dois que entraram) e
    o empate devolve o do cabeçalho, que tem a frase.

    O que ela calou não segura a cor (regra do `_escrever_o_cabecalho` da janela estável): o
    veredito conta os itens que ela NÃO dispensou, senão uma ordem dispensada prenderia o topo em
    laranja e o ⊘ seria botão morto.

    Devolve o dicionário para o :func:`pacote`: a frase em `veredito` e um interruptor por estado.
    VAZIO quando o produto não pôde responder, o que difere de frase vazia (o `escrever()` do piloto
    a traduziria em travessão, a tela afirmando um nada).
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

    O mapa já traduzia os quatro estados do `exame_da_mesa` para as três palavras do desenho dela;
    mora na camada de tela porque é vocabulário, não máquina (o módulo do exame "responde por
    máquina, não por vocabulário"). O import é tardio: `interface.conexoes` puxa a cadeia de tela e
    o topo deste módulo tem de seguir importável numa árvore sem `src/` no caminho.

    A palavra de `problema` ainda é a de `atencao` (02/09/2026)  (noqa-acento)
    por espera do usuário: o mapa manda os dois estados para **AJUSTAR** e ele decidiu que *"o que
    está quebrado agora não pode parecer igual ao que só podia estar melhor"*. A COR já saiu
    (`selo-estado` no :func:`pacote`, regra `.selo.grave` do gerador); a PALAVRA é de produto e
    trocá-la aqui seria escolher no lugar dela. Quando ela disser, muda
    `interface.conexoes.SELO_DO_ESTADO`, o mapa é um só.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.interface.conexoes import SELO_DO_ESTADO

    return SELO_DO_ESTADO.get(estado, _SELO_DESCONHECIDO)


def _dica_da_linha(item: Any) -> str:
    """O `?` de uma linha do Check-up, em HTML: o que importa e a cura.

    Duas metades, não três (02/09/2026: *"o ponto de interrogação para de repetir a linha"*): a
    linha mostra a MEDIÇÃO (`Item.porque`, chave `achado` do :func:`pacote`), então a dica traz o
    que a linha NÃO diz: **por que importa** (`DICAS_DAS_LINHAS`, por chave de regra) e **o que
    fazer** (`PREFIXO_DA_CURA` + `Item.cura`). As frases são do produto, as mesmas constantes de
    `secao_exame._dica_do_item`; aqui só a ORDEM entre elas (uma frase reescrita aqui seria a quarta
    grafia).

    Por que o pacote pede a metade e o dono não muda: `_dica_do_item` é do GTK também
    (`secao_exame.PainelDoExame`), onde a linha mostra `item.rotulo` (o NOME da conferência) e a
    dica é o ÚNICO caminho de `Item.porque` até a tela; cortar a metade do meio no dono apagaria a
    medição da janela estável para curar uma repetição que só existe AQUI.

    Só a quebra de linha é nossa: o dono junta com `\\n\\n` (`set_tooltip_text` do GTK) e em HTML o
    `?` sairia com as frases coladas; `<br><br>` é a tradução, a que o desenho já usa. O texto é
    escapado antes (alvo `html`: `&` ou `<` do exame viraria marcação) por `interface.conexoes._e`,
    o do gerador. O `<b>` do rótulo é o da janela estável e entra DEPOIS do escape (rótulo e texto
    passam por `_e` separados; escapar a frase montada mostraria `<b>`).

    Uma ordem da mesa sem verbete (02/09/2026, o achado de pé: *"o `?` de uma linha sem verbete e
    sem cura abre uma caixa VAZIA de 330px"*): `DICAS_DAS_LINHAS` é indexada por chave de REGRA
    (`energia_do_radio`, `energia_das_portas`, `pareamentos`, `suporte_ao_controle`,
    `vizinhanca_das_portas`) e o item do catálogo de ORDENS traz `chave=ordem.chave` (o slug do
    arranjo, nenhuma delas) e `cura=ordem.acao or None`, talvez vazio; `partes` ficava só com `""` e
    o `?` mostrava o travessão (a decisão 9 tirou a metade do meio e quem não tinha as outras duas
    ficou sem nada).

    A cura é reuso: uma `Ordem` traz TRÊS linhas (`ordens_da_mesa.Ordem.linhas`, rótulos de
    `exame_da_mesa.ROTULOS_DA_ORDEM`: *"O que eu vi aqui"*, *"Por que importa"*, *"Ganho
    esperado"*). A primeira a linha já mostra (`Item.porque`) e fica de fora; as outras duas são o
    que o `?` promete, o par do card do GTK (`secao_exame._linha_da_ordem`) e do `--exame`
    (`exame_da_mesa._imprimir_relatorio`).

    O selo de procedência (`Linha.selo`) não vem: duas frases dividem uma dica de 330px e um
    `[medido]` em cinza competiria com o texto (para quem desenhar a dica maior). O `except` largo é
    de propósito e devolve vazio (o `escrever()` põe o travessão, "não tenho o que dizer aqui"):
    levantar derrubaria a pintura da aba INTEIRA por uma dica, e não emitir a chave deixaria a dica
    do MOCKUP ao lado do achado dela.
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


def _dbm(valor: object) -> int | None:
    """O dBm que a central publicou, ou `None`."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


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
        nome_do_controle=str(ap.get("cor_nome") or ""),
        de_id=str(de["id"]), de_nome=_titulo_do_lugar(de),
        para_id=str(para["id"]), para_nome=_titulo_do_lugar(para),
        controles_no_de=sum(1 for a in aparelhos
                            if a.get("lugar") == de.get("id") and a.get("tipo") == "controle"),
        bons=bons,
        sufocado=bons is not None
        and ar_do_adaptador.nivel_dos_canais(bons) == ar_do_adaptador.NIVEL_ENGASGA,
        pelo_sinal=bool(proposta.get("pelo_sinal")),
        sinal_aqui=_dbm(proposta.get("sinal_aqui")), sinal_la=_dbm(proposta.get("sinal_la")))


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

    Os campos são `rotulo`, `estado` e `porque`, do dataclass `exame_da_mesa.Item`. Um `getattr` com
    reserva (`titulo` com `or str(it)`) é o disfarce perfeito para campo inexistente: não levanta, e
    o `repr` do objeto Python foi parar na tela (foto de 01/09: `Item(chave='energia_do_radio',
    rotulo='Economia de energia desligada', estado='a`).

    A palavra do selo e a dica são do produto (02/09/2026; antes montadas à mão, erradas):

    * o selo saía de `"AJUSTAR" if grave else "CERTO"`, mas o `Item` tem QUATRO estados e
    `interface.conexoes.SELO_DO_ESTADO` os mapeia em TRÊS palavras, e sumia a **NOTA** do `nao_sei`
    (a quarta linha do desenho): "não deu para olhar" chegava como "AJUSTAR", a tela afirmando
    problema que ninguém mediu; * o `?` da linha não era montado (ver `dica` abaixo).
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

    A aba Jogar o chama (`a01_jogar._do_exame`): o aviso do cartão dela sai do MESMO exame desta aba
    (*"duas contagens do mesmo fato divergiriam no primeiro achado novo"*). Medido em 01/09/2026: ao
    dividir a função em `_conferencias()` + `_itens_da_tela()` o nome `_exame` sumiu, o `except
    Exception: return []` do `_do_exame` da Jogar transformou o `AttributeError` em **lista vazia**
    e a Jogar parou de emitir `aviso-selo` e `aviso-texto` sem erro algum (acusou o
    `test_o_casamento_das_dez`: 7 endereços, piso 9). Renomear função privada de um pacote pode
    apagar meia tela de outro, e um `except` largo faz a AUSÊNCIA de dado se ler como "não havia
    achado".

    **A calada não atravessa** (ONDA5-08-01, 06/09/2026): desde a 08-Q5 a ordem dispensada FICA na
    tira desta aba, em cinza, e a filtragem é daqui; sem ela, calar um alarme na Conexões o deixaria
    aceso na coluna **Atenção** da Jogar. É aqui e não em `_itens_da_tela` porque a cura cobre TODOS
    os chamadores sem tocar arquivo de outra posse: a pintura desta aba chama `_itens_da_tela()`
    direto, a 08 continua vendo tudo e a 01 só o que fala (regra paga duas vezes em 05/09).

    **A leitura dos controles também não atravessa** (28/09/2026): a Jogar diz esse fato pelo dono
    (`painel.aviso_do_grab_dobrado`, mesma condição de `home_actions.aviso_de_grab`); a linha desta
    aba só acrescenta a causa.
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

    O dono das frases é `mapa_da_mesa.confissao_do_desenho` (o da janela do desenho). Aqui só a
    CONTA vai à tela, por extenso, depois de :data:`ROTULO_DA_CONTA`; os itens saíram do `title` em
    13/09/2026 (FRASES-E-DICAS-02, eram confissão em primeira pessoa numa dica flutuante) e seguem
    no `?` do topo do mapa.

    Medido em 03/09/2026: a `.mm-conf-linha` está FORA do bloco `.mm-faces` que o pacote troca,
    ninguém a repintava e dizia **"três coisas"** (a cena do mockup) com `title` listando três,
    quando a bancada tem **UMA** lacuna (`especie`). Confissão a mais é tão falsa quanto a que cala.

    `confissao-nada` é o interruptor do sumiço (regra da GTK): a linha SOME quando o desenho
    responde por tudo; zero lacuna viraria *"O que eu não consegui conferir neste desenho: nada."*.
    O dicionário VAZIO é resposta (por isso não é tupla): sem censo não se sabe quantas lacunas há e
    emitir `""` seria PIOR que não emitir, porque o `escrever()` troca vazio por travessão (*"…neste
    desenho: —."*); não emitir deixa a linha como o desenho a escreveu, o único estado honesto
    quando a leitura do barramento falhou.
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

    O desenho é um só (`interface/conexoes.html_do_mapa`), o do gerador do mockup também; muda o
    dado (lá a cena de bancada, aqui o que o usuário declarou), e a extração se provou fiel: página
    regerada byte a byte igual à aprovada. O veredito vem do MOTOR: `veredito_do_quadrado` chama
    `arranjo_da_mesa.julgar` (entrada azul, folga na fileira, extensor; CONFESSA o que não sabe),
    não a reescrita à mão com cinco vereditos digitados que o gerador tinha.
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
               "nova_entrada": _tela.DICA_NOVA_ENTRADA},
        nomes={n: str(p["nome"]) for n, p in logica.portas.items()
               if p.get("filha_de") and p.get("nome")},
        pergunta={"aberta": logica.perguntando_o_hub,
                  "entradas": logica.entradas_para_o_hub()})


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


#: A ordem em que a família dos botões se escreve: sul, leste, oeste, norte, a
#: mesma de ``mesa_viva.LETRAS_DA_FACE`` (e do ✕ ○ □ △ do DualSense).
_FACE_DO_EXTERNO = ("cross", "circle", "square", "triangle")


def a_declaracao_do_externo(entrada: dict[str, Any],
                            declaracao: Any = None) -> dict[str, str]:
    """A cor e a família dos botões que o usuário declarou deste controle externo.

    O-CARTAO-DO-EXTERNO-MOSTRA-O-QUE-ELA-DECLAROU-01 (08/10/2026). A fonte é a da mesa das dez abas
    (`mesa_viva.cor_declarada` e `mesa_viva.familia_dos_botoes`): o externo e o DualSense não
    discordam sobre `controles.cor`, `controles.botoes` e `controles.modo`. A chave é a do
    `maquina.json` (`chave_de_maquina`: o `identity` do daemon, e o `uniq` sem ele); sem endereço
    fixo não há onde declarar e devolve vazio, que não mostra nada.

    ``cor`` é o hex do plástico (``""`` para nome que o mapa não conhece, escrito à mão no
    `maquina.json`: a tela o lista e não o pinta), ``cor_nome`` o nome do mapa e ``botoes``
    ``"xbox"``, ``"nintendo"`` ou ``""`` (nada declarado: o cartão não afirma desenho nenhum).
    """
    vazio = {"cor": "", "cor_nome": "", "botoes": ""}
    try:
        from hefesto_dualsense4unix.app.actions.external_controllers import (
            chave_de_maquina,
        )
        from hefesto_dualsense4unix.integrations.cor_do_plastico import nome_do_aparelho
        from hefesto_dualsense4unix.interface import mesa_viva

        chave = chave_de_maquina(entrada)
        if not chave:
            return vazio
        cor = mesa_viva.cor_declarada(chave, declaracao)
        familia = mesa_viva.familia_dos_botoes(chave, declaracao)
        if cor is None:
            return {**vazio, "botoes": familia}
        slug, nome = mesa_viva.CORES.get(
            str(cor.codigo), (str(cor.id or ""), ""))
        return {"cor": _hex_do_plastico(slug),
                "cor_nome": nome or nome_do_aparelho(cor), "botoes": familia}
    except Exception:
        return vazio


def marcas_do_externo(entrada: dict[str, Any], elemento: str) -> tuple[str, str]:
    """``(atributos da raiz do cartão, a peça dos botões)`` do que o usuário declarou.

    Os DOIS cartões (Jogar e Conexões) chamam só esta função: a cor vira a borda do cartão (a do
    assento é a cor do plástico; a do externo segue tracejada, o «só vê») e a família vira as quatro
    letras da face (sul, leste, oeste, norte). Sem declaração, ``("", "")``: campo sem informação
    não mostra nada.
    """
    ela = a_declaracao_do_externo(entrada)
    atributos = ""
    if ela["cor"]:
        atributos = (f' style="border-color:{ela["cor"]}" '
                     f'title="{html.escape(ela["cor_nome"], quote=True)}"')
    botoes = ""
    if ela["botoes"]:
        from hefesto_dualsense4unix.interface import mesa_viva

        letras = mesa_viva.LETRAS_DA_FACE[ela["botoes"]]
        texto = " ".join(letras[b] for b in _FACE_DO_EXTERNO)
        dica = "Botões declarados"
        botoes = (f'<{elemento} class="ext-botoes" data-botoes="{ela["botoes"]}" '
                  f'title="{dica}">{texto}</{elemento}>')
    return atributos, botoes


#: O que o controle externo pode DECLARAR na Conexões, e o gesto de cada campo. A chave
#: física (`modo`) e o desenho dos botões vêm do `ControleDeclarado`; a cor, dos nomes de
#: fábrica. Vazio na lista = «não sei», e grava `None` (apaga o campo).
_MODOS_DO_EXTERNO = (("xinput", "XInput"), ("dinput", "DInput"), ("switch", "Switch"))
_FAMILIAS_DO_EXTERNO = ("xbox", "nintendo")
GESTOS_DO_EXTERNO = {"modo": "externo-modo", "botoes": "externo-botoes",
                     "cor": "externo-cor"}
#: O rótulo da lista da chave física. NÃO é «Modo»: na casa, Modo é como o controle chega ao
#: jogo (Jogar pelo Hefesto, Conexão Nativa…), e a mesma palavra para o XInput/DInput/Switch do
#: externo faria as duas coisas parecerem uma (o glossário, `docs/A-LINGUA-DESTA-CASA-…`).
ROTULO_DA_CHAVE_DO_EXTERNO = "Chave"


def _nomes_de_cor_do_externo() -> list[str]:
    """Os nomes de fábrica que a tela oferece, sem repetir e na ordem do mapa."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import NOMES_DE_FABRICA

    return list(dict.fromkeys(NOMES_DE_FABRICA.values()))


def _lista_do_externo(gesto: str, quem: str, titulo: str, vazio: str,
                      opcoes: list[tuple[str, str]], atual: str) -> str:
    """Um ``<select>`` da declaração do externo: a primeira opção é «não sei»."""
    itens = [("", vazio), *opcoes]
    if atual and atual not in {v for v, _ in itens}:
        itens.append((atual, atual))
    miolo = "".join(
        f'<option value="{html.escape(v, quote=True)}"'
        f'{" selected" if v == atual else ""}>{html.escape(r)}</option>'
        for v, r in itens)
    dono = html.escape(quem, quote=True)
    return (f'<select class="pronto" data-gesto="{gesto}" data-externo="{dono}" '
            f'title="{html.escape(titulo, quote=True)}">{miolo}</select>')


def declaracao_do_externo_para_editar(entrada: dict[str, Any]) -> str:
    """As três listas (modo, botões, cor) do cartão do externo na Conexões.

    O-CARTAO-DO-EXTERNO-MOSTRA-O-QUE-ELA-DECLAROU-01, item 2. Só o cartão da Conexões escreve (o da
    Jogar só mostra), e só quando o controle tem chave no `maquina.json`; a escolha vale para o
    desenho da tela, nada é remapeado no controle.
    """
    try:
        from hefesto_dualsense4unix.app.actions.external_controllers import (
            chave_de_maquina,
        )
        from hefesto_dualsense4unix.interface import mesa_viva

        chave = chave_de_maquina(entrada)
        if not chave:
            return ""
        quem = str(entrada.get("identity") or entrada.get("uniq") or "")
        declarado = mesa_viva._declarado(chave)
        modo = str(getattr(declarado, "modo", None) or "")
        botoes = str(getattr(declarado, "botoes", None) or "")
        cor = str(getattr(declarado, "cor", None) or "").strip()
        letras = mesa_viva.LETRAS_DA_FACE
        familias = [(f, " ".join(letras[f][b] for b in _FACE_DO_EXTERNO))
                    for f in _FAMILIAS_DO_EXTERNO]
        cores = [(n, n) for n in _nomes_de_cor_do_externo()]
    except Exception:
        return ""
    return (
        '<span class="ext-declara">'
        + _lista_do_externo(GESTOS_DO_EXTERNO["modo"], quem,
                            "Chave do controle: só muda o que a tela mostra",
                            ROTULO_DA_CHAVE_DO_EXTERNO, list(_MODOS_DO_EXTERNO), modo)
        + _lista_do_externo(GESTOS_DO_EXTERNO["botoes"], quem,
                            "Desenho dos botões: nada é remapeado no controle",
                            "Botões", familias, botoes)
        + _lista_do_externo(GESTOS_DO_EXTERNO["cor"], quem,
                            "Cor do controle na tela", "Cor", cores, cor)
        + "</span>")


#: O símbolo do sprite (`aba08.SPRITE_DOS_EXTERNOS`) de cada forma que tem desenho, pela marca de
#: `external_controllers.brand_of` (o dono único; o OUI do 8BitDo vence o VID do modo Switch). O
#: desenho do Pro Controller só vale para o Pro Controller: o Joy-Con, também da Nintendo, não tem
#: aquela forma. O que não tem desenho próprio (Joy-Con, HORI, PowerA, Valve, o genérico) leva o
#: contorno genérico, que não afirma modelo nenhum, e o nome do modelo fica na dica.
SIMBOLO_DO_EXTERNO = {_marcas.MARCA_XBOX: "ext-xbox", _marcas.MARCA_8BITDO: "ext-8bitdo"}
SIMBOLO_DO_PRO = "ext-pro"
SIMBOLO_GENERICO = "ext-generico"


def simbolo_do_externo(entrada: dict[str, Any]) -> str:
    """O símbolo do desenho deste controle de fora: o da forma dele, ou o contorno genérico."""
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        brand_of,
        friendly_type,
    )

    marca = brand_of(entrada)
    if marca == _marcas.MARCA_NINTENDO and friendly_type(entrada).startswith("Pro Controller"):
        return SIMBOLO_DO_PRO
    return SIMBOLO_DO_EXTERNO.get(marca, SIMBOLO_GENERICO)


def desenho_do_externo(entrada: dict[str, Any]) -> str:
    """O quadrado da linha do externo: o desenho do modelo, com o nome dele na dica.

    A-08-MOSTRA-O-DESENHO-DO-CONTROLE-01 (08/10/2026). O modelo vem de `friendly_type`, o mesmo
    dono do título da linha; o texto do modelo não mora na linha, só na dica do quadrado. Todo
    controle de fora tem quadrado, para a coluna dos nomes não mudar de lugar de uma linha à outra.
    """
    from hefesto_dualsense4unix.app.actions.external_controllers import friendly_type

    modelo = html.escape(friendly_type(entrada), quote=True)
    return (f'<span class="ext-desenho" title="{modelo}" role="img" aria-label="{modelo}">'
            f'<svg aria-hidden="true"><use href="#{simbolo_do_externo(entrada)}"/></svg></span>')


def _html_dos_externos(ctx: Contexto) -> str:
    """Uma linha por controle que o Hefesto VÊ e NÃO adota — ``""`` sem nenhum.

    Linha 305 do CSV da paridade: *"uma aba chamada Conexões que não lista metade dos controles
    conectados"*. Quem pergunta é o piloto, no tique lento (`hefesto_vivo._talvez_ler_os_externos`),
    e a resposta chega por `ctx.externos`, campo PRÓPRIO do contexto.

    O conteúdo é o mesmo da aba 01, de propósito: as três frases têm UM dono cada
    (`_format_external_title`, `_format_external_subtitle`,
    `external_controllers.nintendo_bt_warning`), e assim as duas abas não discordam sobre o mesmo
    aparelho (*"a tela afirmando o que não é"*, visto quatro vezes em 31/08). O aviso do
    `hid-nintendo` não acusa o Hefesto nem promete cura: a morte é do driver do kernel com firmware
    clone em modo Switch, a saída estável é o cabo, e nasce só com VID Nintendo E rádio.

    A lista mora dentro da moldura `.gc` (escolha de 06/09/2026, EXTERNOS-01): o CSS da bancada
    (`aba08.py`, `.gc .ext-vaga{display:contents}`) faz a linha virar item; este pacote só devolve
    linhas. Mas ela NÃO é um `.gc-item`: cada um tem `data-controle="pN"`, um rádio de alvo de saída
    e um corpo que se abre, e um externo não tem assento nem o que abrir; um sexto rádio apontaria
    para um aparelho em que o daemon não escreve. Mesma moldura é escolha de DESENHO; ser assento é
    afirmação sobre o aparelho, que esta função não faz. Quem a distingue é a MARCA (o assento diz o
    nome do controle, o externo *"Controle 4 — Nintendo"*), de ``external_controllers.brand_of`` por
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
        """Escapa para HTML pelo `html.escape` da biblioteca, não pelo `_e` da janela GTK.

        `interface.conexoes._e` é esta mesma linha, mas importá-lo seria citação NOVA a uma janela
        que está saindo (`D-0609-GTK-LEVA-INTEIRA`; o portão `nada-aponta-para-a-janela` reprovou a
        primeira volta da sprint, e a lista só diminui). Da janela se reusa o MOTOR (as frases, de
        `app/actions/`), nunca a janela (escolha de `a09_sistema.py`).
        """
        return html.escape(str(x), quote=True)

    fora = []
    for entrada in ctx.externos:
        aviso = nintendo_bt_warning(entrada)
        linha_do_aviso = (f'<span class="ext-aviso">{_e(aviso)}</span>'
                          if aviso else "")
        da_borda, botoes = marcas_do_externo(entrada, "span")
        declara = declaracao_do_externo_para_editar(entrada)
        fora.append(
            f'<div class="ext-linha"{" data-larga" if aviso else ""}{da_borda}>'
            f'{desenho_do_externo(entrada)}'
            f'<span class="ext-nome">{_e(_format_external_title(entrada))}</span>'
            f'<span class="ext-via" title="{_e(_format_external_subtitle(entrada))}">'
            f'{_e(_format_external_subtitle(entrada))}</span>'
            f'{linha_do_aviso}{botoes}{declara}</div>')
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

    O número não se digita (04/09/2026): o desenho cravava *"Custa +16,3 turnos de rádio"*, conferia
    com `radio_da_mesa` então, e no dia em que se remedir o A/B a janela estável acompanha e o HTML
    não. `frase_da_capacidade_do_mic` deriva os quatro números das constantes do medidor (*"o mesmo
    lugar de onde a barra de Rádio em uso tira os dela"*). A frase do custo só entra no rádio, como
    no medidor: pelo cabo o microfone não toca o rádio; o que muda com o transporte é a ROTA e o
    PREÇO, nunca se o microfone existe.
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


#: A recusa estava registrada em `SEM_GESTO` e só aparecia no terminal, a cada
FALA_DO_BOTAO_DO_MIC = {
    True: "O computador inteiro",
    False: "Só este controle",
}


def escopo_do_botao_do_mic(estado: Any) -> str:
    """O que o botão FÍSICO do microfone cala — lido do daemon, um por máquina.

    A chave é `mic_button_toggles_system`, publicada desde o `MIC-EXPOSE-01` (*"o botão de mic deixa
    de ser campo secreto do lifecycle — a GUI/CLI leem o estado efetivo daqui"*; medido em
    04/09/2026: `True`). Ausência devolve vazio, não o padrão do `DaemonConfig`: daemon que não
    respondeu não é daemon que respondeu `True`; o `escrever()` traduz vazio em travessão.
    """
    valor = (estado or {}).get("mic_button_toggles_system")
    return "" if valor is None else FALA_DO_BOTAO_DO_MIC[bool(valor)]


def _texto_da_bateria(bruto: Any) -> str:
    """`100%`, ou o travessão do produto quando ninguém leu.

    O dono é `interface.conexoes.Controle.texto_da_bateria`: a ausência vira **travessão**, não zero
    (*"sem fonte, escreve `— %` em vez de um número herdado"*, regra de
    `status_actions._set_battery_text`). O `Controle` é construído só para isso, com o resto neutro,
    porque `f"{n}%"` aqui seria a segunda grafia e perderia justamente o caso do `None`.
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


# `controller.target.set`, o daemon obedece, e no tique seguinte a tela
# aba. Substituído no lugar, e não guardado ao lado.
TODOS_NA_TELA = "todos"


def _pref_do_alvo(ctx: Contexto) -> str:
    """Qual lugar da mesa a saída está mirando — `p1`..`p4`, ou `todos`.

    A conversão tem duas ordens: o daemon guarda `output_target_index`, a POSIÇÃO em `controllers`
    ("0 = primário", `ipc_handlers.py:3192`); o desenho endereça por `pref`, o NÚMERO do jogador
    desde 20/09/2026 (`mesa_viva._lugares_da_mesa`). Com o P1 fora, o índice 0 é o P2 e o `pref`
    dele é `p2`; divergem sempre que um lugar fica vazio ou o primário não é o de menor número (a
    armadilha de `_indice`, do lado do gesto); a ponte é o `uniq`.

    `None` no daemon é "TODOS", não "não sei" (o campo nasce nulo e é o broadcast). Alvo que o
    `state` não traduz (índice fora da lista, entrada sem `uniq`, controle que saiu entre dois
    tiques) devolve `""`, que **não marca nada**: desmarcar os cinco não afirma, marcar "todos"
    afirmaria um broadcast que o daemon não disse.
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

    A ordem é a do DOM e é o contrato: o piloto distribui uma lista pelos elementos de mesmo
    `data-campo` na ordem em que os acha (`hefesto_vivo.pintar`, passo 1); o gerador escreve
    `#gc-todos` e depois um por lugar da mesa, logo `[todos, p1, p2, p3, p4]`. Vai em todo tique,
    inclusive toda vazia (regra do botão cinza da ONDA0-F e das listas do ⊘): chave que só aparece
    quando há o que dizer deixa a marca do tique anterior, e um acordeão que abrisse sozinho num
    lugar sem dono afirmaria o que não é.
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

    O dono é `status_actions.texto_de_controle_nao_adotado`, que já devolve `""` quando não há o que
    dizer (daemon sem resposta, payload torto, daemon antigo sem a chave, quantidade zero); repetir
    as guardas seria a segunda grafia da regra. Substitui uma emissão morta em dois níveis (medido
    em 04/09): `"sem_driver": st.get("controles_sem_driver")` é um `dict`, que `pacotes.normalizar`
    descarta, para um endereço que página nenhuma tinha; o defeito (dois DualSense ligados, a janela
    mostrando um, sem pista do porquê) voltava inteiro no HTML.
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

    Dois donos: `home_actions.controles_bt_frageis` lê a lista publicada e `texto_native_bt_fragil`
    a vira frase. *"lista vazia não quer dizer 'nenhum frágil' — quer dizer 'não sei quais'"*, por
    isso quem chama olha TAMBÉM o booleano `native_bt_fragil`, e o aviso acende sem nomes em vez de
    calar. O `fragil` por controle diria QUAL, não O QUE FAZER; a frase do dono diz quem é e a saída
    (o cabo, ou voltar à emulação), e é ela que a aba Início acende.
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

    da_mesa = {str(m.get("uniq") or ""): m for m in ctx.mesa}

    nomes = nome_do_jogador.nomes_dos_donos()
    modo_da_mesa: str | None = None
    colunas = {}
    comeco_da_gestao = time.perf_counter()
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
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
            # DESLIGADA no `maquina.json` do usuário (medido em 03/09), a tela
            "mic-caminho": caminho_do_microfone(str(c.get("transport") or "")),
            # O `title` DA LINHA DO MICROFONE — ver :func:`dica_do_microfone`. O
            "mic-dica": dica_do_microfone(str(c.get("transport") or "")),
        }
        if modo_da_mesa is None:
            modo_da_mesa = modo_da_fileira(st)
        colunas[uniq].update(estado_do_controle(c, eu, st, declaracao, modo_da_mesa))
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
        "sem_dono": {},
        # que o `alvo-aberto` marca — as ressalvas contam mesmo caladas, porque
        "cobertura": {"pintados": 1 + 2 + 5 + len(confissao)
                      + 1 + 12
                      + sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }


#      a trava de `mic-existe` e `vizinho-o-que-e`, e os dois estão ligados.
#      (`Disconnect` do BlueZ por D-Bus, `integrations/gesto_de_reconexao.py`).
#      **Foi exatamente essa a cura de `vizinho-o-que-e`**: em vez de ligar o
from . import gesto  # noqa: E402
from .a02_controles import mudo as _o_mudo_da_aba_02  # noqa: E402

# `integrations/gesto_de_reconexao.py`, que roda `busctl` e não passa pelo
# de quem faça. O `gesto_de_reconexao` faz, é puro, mascara o endereço e devolve
#: Vazio desde 08/10/2026 (AS-QUATRO-LINHAS-DA-08-SEM-DONO-GANHAM-DONO-OU-SAEM-DO-DESENHO-01):
#: nenhum botão do desenho da 08 fica sem atendente. Os quatro que ficavam saíram do gerador, pela
#: razão que cada um já trazia, e o que o produto sabe fica como marca, sem botão:
#: * `novo-hub` («Acrescentar hub»): a `LogicaDoMapa` não tem `acrescentar_hub` e a pergunta
#:   «ligado em que entrada» não tinha onde ser feita; o botão saiu, e a face «Hubs e extensões»
#:   continua a mostrar o que há;
#: * `custo-som` e `custo-vibracao`: a ponte de rádio sobe quando o JOGO manda som ou vibração ao
#:   controle (`radio_governador`) e não há interruptor por controle; um botão que a desligasse
#:   brigaria com o jogo no tique seguinte. Viraram marcas (`<span data-ligada>`) que mostram qual
#:   das duas a ponte carrega, com a dica de sempre;
#: * `custo-luz`: a barra de luz não custa rádio que se meça (viaja no relatório de saída que o
#:   controle já recebe), e o interruptor dela mora na aba Iluminação. Virou marca.
SEM_GESTO: dict[str, str] = {}


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde o usuário clicou. Vazio = clique solto, e recusa."""
    return str(o.get("uniq") or "")


def _indice(ctx: Contexto, uniq: str) -> int | None:
    """A posição daquele controle em `controllers` — o que o daemon numera.

    **Não é o número do jogador.** `controller.target.set` pede `index`, "posição em `controllers`,
    0 = primário" (`ipc_handlers.py:3192`); `status_actions._controller_target_rows:1579` ORDENA a
    lista pelo número de identidade e CARREGA o `index` da enumeração em cada linha (*"a usuária
    clicaria no chip do 1 e editaria outro controle"*). O `index` vem publicado por entrada (o campo
    de `ipc_handlers._numero_de_exibicao:526`); sem ele, a posição na lista é a mesma conta, e
    `None` quando nem isso: o gesto recusa dizendo, em vez de mirar o 0 e trocar o controle do
    usuário.
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

    `ipc_bridge.machine_declare:861` devolve `(ok, motivo)` com o motivo já em frase de tela
    (`_MOTIVOS_MAQUINA`), o que faz o botão RECUSAR DIZENDO em vez de gravar calado. O guarda existe
    porque o dublê da régua (`tests/unit/test_os_botoes_tem_dono.PonteDeMentira`) devolve `True`
    para todo nome que não seja `identity…_set`: desempacotar às cegas levantaria `TypeError` dentro
    do teste.
    """
    if isinstance(r, tuple):
        ok, motivo = [*r, None, None][:2]
        return bool(ok), str(motivo or "")
    return bool(r), ""


def _declarar(p: Any, mesa: dict[str, Any]) -> None:
    """Grava um pedaço da declaração da mesa, na hora.

    Decisão de 01/09/2026: **clicar já aplica**, sem rascunho à espera de "Aplicar". A GUI estável
    acumula em `_maquina_pendente` (`secao_mesa._ao_declarar:1467`) porque lá o rodapé grava e
    `machine.declare` daria um segundo dono do gesto; aqui o dono é o clique.

    A declaração é parcial, o que a torna segura: o daemon funde contra o disco sob lock
    (`ipc_handlers._handle_machine_declare:5254`), então `{"mesa": {"altura_da_antena": …}}` não
    apaga `linha_de_visada`, rádios nem o mapa do gabinete.

    Com o Hefesto desligado, a resposta desce ao disco (28/09/2026): a ponte devolve `(False, None)`
    sem serviço e o gesto recusava, perdendo altura da antena, visada e nome de vizinho sobre um
    arquivo que não depende dele. Grava `lugar_declarado.declarar_a_mesa` (mesmo lock e fusão,
    `gravar_rascunho_da_mesa`; o daemon lê o arquivo ao ligar), o desvio do «Aplicar» do rodapé
    (`footer_actions._gravar_declaracao_de_maquina`), só quando o serviço NÃO respondeu: serviço que
    respondeu e recusou segue recusando, ou a memória dele divergiria do arquivo.
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

    É o `title` do número e do aparelho de cada cartão (*"Escolhe só este controle: a luz, os
    gatilhos e a vibração passam a mirar nele. A fita do topo passa a apontar para ele."*), e
    `controller.target.set` faz isso (`daemon/ipc_handlers.py:3196`: *"Com o alvo setado,
    lightbar/gatilhos/player-LED/rumble/mic-LED passam a mirar SÓ aquele controle"*), o método do
    seletor da GUI estável (`app/actions/status_actions.py`). Sem função no `ipc_bridge` (degrau 3
    da ponte), passa pelo mesmo `_safe_call` e timeout.

    A fita do topo acompanha no tique seguinte, não por este gesto: o destaque do chip vem do
    `:checked` do acordeão, que :func:`_alvo_de_saida` marca pelo alvo guardado no daemon, e as
    regras do gerador acham o chip pelo número do jogador (`data-pref`,
    A-GESTAO-SEGUE-O-JOGADOR-01).
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

    O `title` é o contrato (*"Fecha. A fita volta para «Todos» e todos abrem juntos."*). No daemon
    "Todos" é `index: null` (`ipc_handlers.py:3262-3263`), o `None` da linha 0 do seletor da GUI
    estável (`status_actions._controller_target_rows:1586`). Não precisa do `uniq`, único desta aba
    assim ("todos" não tem sujeito); exigir um prenderia a saída no último controle escolhido quando
    ela fechasse a linha pela seta.
    """
    p.chamar("controller.target.set", index=None)


@gesto("08-conexoes.html", "sala-altura")
def sala_altura(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"O dongle fica acima da cabeça de quem joga sentado?" — grava a resposta.

    Uma das duas coisas que barramento nenhum responde, logo DECLARADA:
    `MesaDeclarada.altura_da_antena` (`utils/maquina.py:141`), só `"acima"`, `"abaixo"` ou `None`.
    `exame_da_mesa.vizinhanca_das_portas` a recebe e muda a linha do Check-up desta aba.

    O `data-modo` traz o id do esquema e `""` ("Não sei") vira `None` aqui: a string `"nao_sei"`
    faria o pydantic recusar o documento INTEIRO (`extra="forbid"` + `Literal`) e a tela diria "não
    consegui gravar" em vez de "valor inválido" (razão de `secao_mesa._valor_do_seletor:1498`).
    """
    escolha = str(o.get("modo") or "")
    if escolha not in ("acima", "abaixo", ""):
        raise ValueError(f"sala-altura: {escolha!r} não é resposta desta pergunta")
    _declarar(p, {"altura_da_antena": escolha or None})


@gesto("08-conexoes.html", "sala-visada")
def sala_visada(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Tem gente sentada entre o dongle e o sofá?" — grava a resposta.

    O par da altura: `MesaDeclarada.linha_de_visada` (`utils/maquina.py:150`), `"com_gente"` /
    `"livre"` / `None`. Corpo humano absorve 2,4 GHz e nenhum barramento sabe. É gesto separado
    porque são duas perguntas: um gesto único mandaria as duas chaves e a não respondida iria como
    `None`, que na fusão é uma ESCOLHA ("voltei para 'Não sei'"), não ausência
    (`utils/maquina.fundir_declaracao:650`); responder "Sim" na altura apagaria a visada, calado.
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

    É do `secao_controles` e separada da do cabo de propósito: *"no cabo não FAZ FALTA, sem endereço
    não TEM ONDE ser guardada. Uma frase só para os dois mandaria a pessoa procurar cabo onde o
    problema é endereço."*
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

    Não é o `mic.set`, que é o MUDO no firmware (`ipc_handlers._handle_mic_set`: acende a luz
    vermelha e o PipeWire segue publicando a fonte). Aqui a promessa é *"Desligado, nenhum programa
    o enxerga"*, a PONTE: `ControleDeclarado.microfone` no `maquina.json` (`utils/maquina.py:589`),
    decisão de 22/08/2026 (*"por controle"*). O clique vale AGORA: `_handle_machine_declare` relê o
    disco, rebinda `daemon._maquina` e sobe ou desce o subsystem `bt_mic` no mesmo pedido
    (`ipc_handlers.py:4972`, QUATRO-MICROFONES-01: *"o 'Aplicar' tem de VALER agora"*).

    **Desligar grava `False`** (18/09/2026, a inversão): gravava `None` enquanto o default era
    silêncio, mas com a ordem *"todos os controles tem que nascer com tudo mic, giroscopio e afins"*
    a ausência LIGA e `None` seria o botão que não desliga. O `false` no disco é o único registro de
    que o usuário disse não e impede o produto de religar sozinho no próximo boot
    (`bt_mic.uniqs_recusados`).

    Não entrega: pelo CABO o microfone não passa por esta ponte (`secao_controles.DICA_MIC_NO_CABO`:
    *"Só vale no rádio. Pelo cabo o microfone deste controle é uma placa de som USB e não passa por
    esta ponte — ele já funciona sem ela."*). A GUI estável apaga o interruptor no cabo
    (`pode_ligar_o_mic`); aqui grava, porque a declaração é sobre o CONTROLE e vale quando ele
    voltar ao rádio. O aviso na tela é da aba.
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


def _declarar_do_externo(ctx: Contexto, o: dict[str, Any], p: Any, campo: str,
                         validos: set[str]) -> None:
    """Grava ``controles[chave].<campo>`` de um controle externo, pelo `machine.declare`.

    O-CARTAO-DO-EXTERNO-MOSTRA-O-QUE-ELA-DECLAROU-01, item 2 (08/10/2026). O caminho é o do
    `mic-existe` (o daemon funde contra o disco sob lock, relê e responde). A chave NÃO vem do
    clique: sai do controle que a tela tem agora (`data-externo`: o `identity` ou o `uniq`), e
    controle que não está mais aqui recusa, em vez de gravar sob endereço que ninguém escolheu.
    Lista em branco = «não sei» e grava ``None``, que apaga o campo.
    """
    from hefesto_dualsense4unix.app.actions.external_controllers import chave_de_maquina

    nome = GESTOS_DO_EXTERNO[campo]
    uniq = str(o.get("externo") or "")
    if not uniq:
        raise ValueError(f"{nome}: o clique não disse em qual controle")
    entrada = next((e for e in (*ctx.externos, *ctx.conectados)
                    if uniq in (str(e.get("identity") or ""), str(e.get("uniq") or ""))),
                   None)
    chave = chave_de_maquina(entrada) if entrada else ""
    if not chave:
        raise RuntimeError("Este controle não está mais aqui, ou não tem endereço fixo; "
                           "sem ele a escolha não tem onde ser guardada.")
    escolha = str(o.get("valor") or "").strip()
    if escolha and escolha not in validos:
        raise ValueError(f"{nome}: {escolha!r} não é resposta desta lista")
    ok, motivo = _resposta(
        p.machine_declare({"controles": {chave: {campo: escolha or None}}}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o que você declarou")
    _reler_a_declaracao()


@gesto("08-conexoes.html", "externo-modo", grava="machine_declare")
def externo_modo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Modo: XInput / DInput / Switch" — a chave física do controle externo."""
    _declarar_do_externo(ctx, o, p, "modo", {v for v, _ in _MODOS_DO_EXTERNO})


@gesto("08-conexoes.html", "externo-botoes", grava="machine_declare")
def externo_botoes(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Botões: A B X Y / B A Y X" — só o desenho da tela; nada é remapeado."""
    _declarar_do_externo(ctx, o, p, "botoes", set(_FAMILIAS_DO_EXTERNO))


@gesto("08-conexoes.html", "externo-cor", grava="machine_declare")
def externo_cor(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Cor" do controle externo, pelos nomes de fábrica que a tela oferece."""
    _declarar_do_externo(ctx, o, p, "cor", set(_nomes_de_cor_do_externo()))


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


@gesto("08-conexoes.html", "aparelho-tipo", grava="machine_declare")
def aparelho_tipo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """«O que é este aparelho?»: a pessoa diz o tipo de um aparelho do Bluetooth sem tipo.

    A chave é o endereço do aparelho que a tela tem agora (nunca um texto do clique), e o valor, uma
    das nove palavras da grade. O que se guarda vence a adivinhação a cada leitura.
    """
    ap = _aparelho_na_tela(str(o.get("alvo") or ""))
    chave = _so_hex(str(ap["id"])).lower()
    if not chave:
        raise ValueError("aparelho-tipo: o aparelho não tem endereço para guardar a escolha")
    escolha = str(o.get("valor") or "").strip()
    if not escolha:
        return {"armou": True}
    if escolha not in {guarda for _, guarda, _ in TIPOS_DA_GRADE}:
        raise ValueError(
            f"aparelho-tipo: {escolha!r} não é uma das respostas da grade "
            f"({sorted(g for _, g, _ in TIPOS_DA_GRADE)})")
    declaracao = {"aparelhos": {chave: {"tipo": escolha}}}
    ok, motivo = _resposta(p.machine_declare(declaracao))
    if not ok and not motivo:
        # Hefesto desligado: a escolha desce ao disco, que o daemon lê ao ligar (como `_declarar`).
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_maquina

        ok = declarar_a_maquina(declaracao).gravou
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o que você declarou")
    _reler_a_declaracao()
    return None


@gesto("08-conexoes.html", "usar-como-botoes")
def usar_como_botoes(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Usar como botões de…»: arma a janela do acionador com o que o `maquina.json` já diz dele."""
    global _RASCUNHO
    ap = _aparelho_na_tela(str(o.get("alvo") or ""))
    if ap.get("tipo") != TIPO_ENTRADA:
        raise ValueError(f"usar-como-botoes: {ap.get('id')!r} não é um aparelho de entrada")
    with _TRAVA_DO_RASCUNHO:
        _RASCUNHO = _rascunho_da_linha(ap, _quem_recebe(_CENA_NA_TELA))
    return {"armou": True}


@gesto("08-conexoes.html", "acionador-nova-tecla")
def acionador_nova_tecla(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Esperar a próxima tecla»: a tecla chega numa thread e entra na lista, já escolhida."""
    global _RASCUNHO
    r = _o_rascunho()
    if r.esperando:
        return {"armou": True}
    evento = _evento_do_acionador(r.chave)
    if evento is None:
        raise RuntimeError("o aparelho não está ligado nesta máquina")
    with _TRAVA_DO_RASCUNHO:
        _RASCUNHO = r
        r.esperando = True
    threading.Thread(target=_esperar_a_tecla, args=(r, evento), name="acionador-tecla",
                     daemon=True).start()
    return {"armou": True}


@gesto("08-conexoes.html", "acionador-botao")
def acionador_botao(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Um botão do desenho: a tecla escolhida na lista passa a cair nele."""
    global _RASCUNHO
    r = _o_rascunho()
    botao = botao_da_peca(str(o.get("entrada") or ""))
    if botao is None:
        raise ValueError(f"acionador-botao: {o.get('entrada')!r} não é um botão que a troca "
                         "conhece")
    bruta = o.get("forma")
    forma: dict[str, Any] = bruta if isinstance(bruta, dict) else {}
    escolhida = str(forma.get("tecla") or (r.sel if r.sel is not None else ""))
    if not _CODIGO_DE_TECLA.match(escolhida):
        raise ValueError("acionador-botao: nenhuma tecla da lista está escolhida")
    with _TRAVA_DO_RASCUNHO:
        linha = next((t for t in r.teclas if t[0] == int(escolhida)), None)
        if linha is None:
            raise ValueError(f"acionador-botao: a tecla {escolhida} não está na lista")
        linha[2] = botao
        r.sel = int(escolhida)
        quem = str(forma.get("acionador-quem") or "")
        if _CHAVE_DE_CONTROLE.match(quem):
            r.controle = quem
        _RASCUNHO = r
    return None


@gesto("08-conexoes.html", "acionador-guardar", grava="machine_declare")
def acionador_guardar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Guardar»: o controle e as teclas vão ao `maquina.json`, pela chave do kernel."""
    global _RASCUNHO
    r = _o_rascunho()
    bruta = o.get("forma")
    forma: dict[str, Any] = bruta if isinstance(bruta, dict) else {}
    controle = str(forma.get("acionador-quem") or r.controle)
    if not _CHAVE_DE_CONTROLE.match(controle):
        raise ValueError(f"acionador-guardar: {controle!r} não é um controle da mesa")
    if not r.chave:
        raise ValueError("acionador-guardar: o aparelho não tem a chave do kernel")
    teclas: dict[str, str | None] = {str(c): b for c, _, b in r.teclas if b}
    antes = getattr((getattr(_declaracao(), "acionadores", None) or {}).get(r.chave),
                    "teclas", None) or {}
    teclas.update({c: None for c in antes if c not in teclas})
    nome = r.nome if r.nome != ACIONADOR_SEM_NOME else None
    declaracao = {"acionadores": {r.chave: (
        {"nome": nome, "controle": controle, "teclas": teclas}
        if any(teclas.values()) else None)}}
    _declarar_o_acionador(p, declaracao)
    with _TRAVA_DO_RASCUNHO:
        _RASCUNHO = None
    return None


def _declarar_o_acionador(p: Any, declaracao: dict[str, Any]) -> None:
    """O `machine.declare` do acionador; com o Hefesto desligado, desce ao disco (`_declarar`)."""
    ok, motivo = _resposta(p.machine_declare(declaracao))
    if not ok and not motivo:
        perfil._com_o_src()
        from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_maquina

        ok = declarar_a_maquina(declaracao).gravou
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o que você declarou")
    _reler_a_declaracao()


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

    Não é botão morto: a primeira leva dizia que o exame já roda a cada tique em `_exame()`, o que
    valia para TRÊS conferências; o exame tem cinco mais as ordens de serviço, e as outras três não
    cabem no tique: `pareamentos` forka `busctl` (teto de 5 s, `ESPERA_DO_BUSCTL_S`) e `ler_a_mesa`
    proíbe tique no próprio docstring. O botão cumpre o `title` (*"refaz o exame das entradas —
    energia e rádio — e repinta os selos, as linhas e as ordens de serviço"*) e traz:

        pareamentos            `busctl`, os pareamentos salvos do BlueZ
        vizinhanca_das_portas  a linha que a altura da antena e a visada mudam
        ordens de serviço      `ordens_da_mesa.catalogo`, varredura do barramento
        os rádios vizinhos     `ler_a_mesa`, que endereça o "— O que é? —"

    Não fala com o daemon (sysfs + `busctl`, função pura), por isso está em `SEM_ECO`: o que muda é
    a tira do Check-up, no tique seguinte. Roda na thread do gesto (`hefesto_vivo` dispara cada
    gesto num `threading.Thread`), disciplina do `secao_exame.reexaminar`: um `subprocess.run`
    síncrono na thread do GTK congelou a janela por 10 s.

    O corpo é :func:`_correr_o_exame_completo` (03/09/2026, `MIGRA-08-01`), também usado na ENTRADA
    da aba (:func:`_pedir_o_exame_de_entrada`). Relê os controles (26/09/2026,
    `D-2609-O-ATUALIZAR-ENTRA-NO-EXAMINAR`: *«não existe diferença entre o examinar entradas e
    atualizar»*): os nomes dos donos no BlueZ e o rascunho do mapa das portas; a declaração o exame
    já relê.
    """
    global _LOGICA
    em_fundo.esquecer("bluez")
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

    O resultado é do daemon (``primary_grab_state``), a condição é do dono
    (`home_actions.aviso_de_grab`: principal conectado, controle do Hefesto de pé e grab que
    FALHOU), e a frase da linha e a do `?` também (:func:`_o_porque_e_a_cura_do_dono`). Sem aviso
    não há linha.

    A causa é do exame (28/09/2026): pergunta à porta do broker (`porta_provavel`) e ao nó
    (`estado_do_grab`) e escreve no diário as duas linhas de cabeçalho da casa (`linha_da_porta`,
    `linha_do_grab`) com a leitura que um zero valeria (`leitura_de_zero`): «PEGO por outro
    processo» não é «não posso ler». Só pergunta ao nó quando o daemon JÁ disse que não conseguiu o
    grab, ou seja outro processo o segura.
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
    por_endereco = {nome_do_jogador.mac(chave): str(no)
                    for chave, no in (nos or _nos_dos_controles)().items()}
    caminho = por_endereco.get(nome_do_jogador.mac(primario.get("uniq")))
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

    Interruptor desde 06/09/2026 (decisão 08-Q5): *"A recomendação calada continua no lugar dela, em
    cinza, e o mesmo botão desfaz."* Antes só calava: o único escritor de `ordens_dispensadas` era
    este gesto (*"Hoje não há caminho de volta nenhum"*).

    | estado da linha | grava | memória |
    | --- | --- | --- |
    | falando | `{"quando": hoje, "arranjo": ordem.arranjo}` | `_DISPENSADAS[chave] = arranjo` |
    | calada | `{"quando": "", "arranjo": ""}` | `_DISPENSADAS[chave] = ""` |

    Desfazer é escrever `arranjo=""`, não remover a chave: `machine.declare` não tem verbo de
    remoção (nota de :data:`_DISPENSADAS`). O esquema aceita os dois vazios
    (`OrdemDispensada._so_a_data` só cobra a forma do que NÃO é vazio) e arranjo vazio não casa com
    arranjo algum, logo a ordem volta a falar; a marca fica no registro e a REGRA decide se ela
    cala. O "deu certo" é a própria linha mudando de cor, sem o pisca-verde de 1,5 s da 03-Q4
    (aquele é para gesto cuja resposta não se vê).

    Tem dono: `MesaDeclarada.ordens_dispensadas[chave] = {quando, arranjo}` (`utils/maquina.py`), o
    que `secao_exame._gravar_a_dispensa` escreve. A chave é o ARRANJO, não a recomendação:
    `ordens_da_mesa.ordens_novas` compara o arranjo GUARDADO com o de agora, a dispensa vale para o
    FATO e, mudando o cabo, a ordem volta sozinha (sem isso o botão viraria "grava e não cala"; o
    que destravou o ⊘ da primeira leva foi existir `Item.ordem` na tela, pois o **Examinar Portas**
    traz o catálogo). Uma CONFERÊNCIA não se dispensa (`energia_do_radio`, `pareamentos`,
    `suporte_ao_controle`… respondem *"está certo?"*, só a ORDEM responde *"faça isto"* e tem
    arranjo): o ⊘ nela recusa dizendo, pois gravaria chave que regra nenhuma consulta.

    `quando` é só a data: a hora não decide nada e seria dado a mais sobre a rotina dela num arquivo
    que ela cola em relato de defeito (`OrdemDispensada._so_a_data` reprova outra forma). A linha
    muda na hora: a decisão entra em `_DISPENSADAS` antes de o próximo tique montar a tira. **A
    ordem das duas escritas não se inverte**: `_declarar` LEVANTA quando o daemon recusa e a memória
    só muda depois; invertido, a tela ficaria num estado que o disco não tem e a linha cinza
    voltaria sozinha no tique seguinte, sem uma palavra (perder trabalho dela em silêncio).
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
# `_handle_machine_declare` (`daemon/ipc_handlers.py:4972`) → `maquina.json`, e


def _gravar_o_mapa(p: Any) -> None:
    """Manda ao daemon o rascunho inteiro do mapa, e RECUSA DIZENDO se não deu."""
    ok, motivo = _resposta(p.machine_declare({"mapa": _logica_do_mapa().como_documento()}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o desenho do gabinete")


@gesto("08-conexoes.html", "escolher-aparelho")
def escolher_aparelho(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Primeiro tempo: o aparelho vai para a mão do usuário. Clicar de novo desescolhe.

    Não grava nada, único dos seis: escolher é estado de tela e o que vai ao disco é o segundo
    tempo. Está no `SEM_ECO` por razão diferente dos outros cinco (que não ecoam porque o
    `state_full` não publica o `mapa`): este não chama a ponte (medido com dublê em 02/09/2026, o
    clique dirigido `caminho="3-1.1.4"` fez ZERO chamadas). O endereço é o CAMINHO do kernel
    (`data-caminho`), não o rótulo: os dois adaptadores Bluetooth da bancada são o mesmo modelo e só
    o caminho os distingue (`rotulo_do_aparelho`).
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


@gesto("08-conexoes.html", "novo-hub")
def novo_hub(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Abre a pergunta curta do hub: em qual entrada ele está, e o nome, se ela quiser.

    Não grava (abrir é estado de tela); o que vai ao disco é o `novo-hub-gravar`.
    """
    if not _logica_do_mapa().perguntar_o_hub():
        raise RuntimeError(
            "não há entrada no desenho do gabinete onde ligar um hub — acrescente "
            "uma entrada a uma face antes.")


@gesto("08-conexoes.html", "novo-hub-cancelar")
def novo_hub_cancelar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Fecha a pergunta do hub sem acrescentar nada."""
    _logica_do_mapa().desistir_do_hub()


@gesto("08-conexoes.html", "novo-hub-gravar", grava="machine_declare")
def novo_hub_gravar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Liga o hub na entrada escolhida: nasce a filha dela, com o nome, e vai ao disco."""
    from hefesto_dualsense4unix.utils.rotulo_da_entrada import MAXIMO_DO_NOME_DA_ENTRADA

    forma_lida = o.get("forma")
    forma: dict[str, Any] = forma_lida if isinstance(forma_lida, dict) else {}
    numero = str(forma.get("hub-entrada") or "").strip()
    if not numero:
        raise ValueError("a pergunta não disse em qual entrada o hub está ligado.")
    nome = str(forma.get("hub-nome") or "")
    if len(" ".join(nome.split())) > MAXIMO_DO_NOME_DA_ENTRADA:
        raise RuntimeError(
            f"O nome do hub tem até {MAXIMO_DO_NOME_DA_ENTRADA} letras.")
    if not _logica_do_mapa().acrescentar_hub(numero, nome):
        raise RuntimeError(
            f"não dá para ligar um hub {_a_entrada_na_frase(numero, em=True)}: ou ela não "
            f"está no desenho, ou já é filha de outra — não há neta.")
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
    CAUSA_LONGE_PAUSADA,
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
    CAUSA_LONGE_PAUSADA: ("Movimento por segundo: longe do adaptador, som e vibração "
                          "pausados para não perder botão"),
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
CONECTADO = "Conectado"
USB = "USB"
ESQUECER = "Esquecer"
MENU_DA_LINHA = "\u22ee"
#: os dois o «Tentar de Novo» aparecia aceso e tremia.
ESPERA_NA_TELA_S = _central_do_radio.PRAZO_DO_PENDENTE_S
LEMBRA_O_NAO_CONECTOU_S = _central_do_radio.LEMBRA_O_NAO_CONECTOU_S
VOLTAS_DO_VIGIA_NA_TELA = 3

#: A CATEGORIA DO APARELHO DE BAIXA ENERGIA QUE NÃO DIZ O TIPO
#: (O-ACESSORIO-SEM-TIPO-GANHA-CATEGORIA-E-SINAL-NA-CONEXOES-01): o nome «Acessório» é do
#: usuário (09/10/2026, 16h). O glifo, a palavra, a cor e a legenda dela moram nesta tabela só,
#: e as tabelas por tipo abaixo a leem. Quem dá a categoria é a cena, onde o tipo e o enlace se
#: encontram (:func:`_com_a_categoria_do_enlace`), nunca o nome ou a marca do aparelho. As cores
#: são os tokens da raiz da aba (O-TEMA-DE-CORES-ENTRA-PELA-FOLHA-DE-USUARIO-01): o valor mora em
#: `aba08.CORES_NA_SALA` e `aba08.CORES_NA_REGUA`, onde um tema também os alcança.
TIPO_ACESSORIO = "acessorio"
CATEGORIA_ACESSORIO = {"glifo": "acessorio", "palavra": "acessório", "legenda": "Acessório",
                       "cor": f"var(--sala-{TIPO_ACESSORIO})",
                       "cor_na_regua": f"var(--c-{TIPO_ACESSORIO})"}

#: O glifo de cada tipo, numa tabela só: a antena (`radio`) é do adaptador e de
#: mais ninguém, e o tipo sem desenho (`outro`, `nao_sei`, o que ninguém nomeou) é o «?».
GLIFO_DO_TIPO = {
    "teclado": "teclado", "mouse": "mouse", "caixa": "caixa", "caixa_de_som": "caixa",
    "fone": "fone", "webcam": "webcam", "wifi": "wifi", "celular": "celular",
    "relogio": "relogio", TIPO_ACESSORIO: CATEGORIA_ACESSORIO["glifo"],
    "gamepad": "ds", "entrada": "botoes",
}


def glifo_do_tipo(tipo: object) -> str:
    return GLIFO_DO_TIPO.get(str(tipo or ""), "ajuda")


TIPO_PELO_ICONE = {
    "input-keyboard": "teclado", "input-mouse": "mouse", "input-tablet": "mouse",
    "audio-headset": "fone", "audio-headphones": "fone", "audio-card": "caixa",
    "camera-video": "webcam", "camera-photo": "webcam", "phone": "celular",
    "input-gaming": "gamepad",
}
PALAVRA_DO_TIPO = {"teclado": "teclado", "mouse": "mouse", "fone": "fone",
                   "caixa": "caixa de som", "webcam": "webcam", "outro": "aparelho",
                   "celular": "celular", "relogio": "relógio",
                   TIPO_ACESSORIO: CATEGORIA_ACESSORIO["palavra"], "gamepad": "controle",
                   "entrada": "aparelho de entrada"}

#: A grade «O que é este aparelho?» (desenho do todo, 13/10/2026): `(rótulo, guardado, glifo)`.
#: O que se guarda é o ``AparelhoDeclarado.tipo`` do ``maquina.json``; «Controle» desenha-se na
#: linha com o glifo do DualSense, mas o aparelho NÃO vira o controle do Hefesto (sem ponte, sem
#: perfil): quem a pessoa diz que é controle de outra marca é só um aparelho com nome.
TIPOS_DA_GRADE: tuple[tuple[str, str, str], ...] = (
    ("Controle", "controle", "ds"), ("Fone", "fone", "fone"), ("Caixa de som", "caixa", "caixa"),
    ("Teclado", "teclado", "teclado"), ("Mouse", "mouse", "mouse"),
    ("Celular", "celular", "celular"), ("Relógio", "relogio", "relogio"),
    ("Acessório", TIPO_ACESSORIO, "acessorio"), ("Outro", "outro", "ajuda"),
)
#: O que se guarda → o tipo que a linha usa (só «controle» muda de nome).
TIPO_DA_LINHA_PELA_ESCOLHA = {"controle": "gamepad"}
SEM_TIPO = "Sem tipo"
SEM_TIPO_DICA = "O Bluetooth não disse o que ele é"
SEM_NOME = "Aparelho sem nome"


def html_da_grade_de_tipos() -> str:
    """A janela «O que é este aparelho?»: nove ícones grandes; o alvo chega no clique do «?»."""
    opcoes = "".join(
        f'<button class="tipo-op" data-gesto="aparelho-tipo" data-alvo="" value="{_x(guarda)}">'
        f'{_ic(glifo, "ds" if glifo == "ds" else "")}<span>{_x(rotulo)}</span></button>'
        for rotulo, guarda, glifo in TIPOS_DA_GRADE)
    return (
        '<div class="tela-nova" id="tipo-do-aparelho">'
        '<div class="tn-cx tipo-cx" role="dialog" aria-modal="true" '
        'aria-label="O que é este aparelho">'
        '<div class="tn-topo"><span class="tn-tit">O que é este aparelho?</span>'
        '<a class="tn-x" href="#" data-dica="Fechar">\u00d7</a></div>'
        f'<div class="tn-corpo"><div class="tipo-grade">{opcoes}</div></div>'
        '</div></div>')
# --- Os acionadores: um aparelho de entrada vira botões de um controle -----------------------
#
# OS-ACIONADORES-USB-ENTRAM-COMO-BOTOES-DO-CONTROLE-01 (desenho r3-08-14). A linha do aparelho de
# entrada leva «Usar como botões de…», que abre a janela `#acionador`: a lista das teclas, o
# controle que as recebe (pelo plástico) e o desenho real do DualSense, onde cada tecla escolhe o
# botão em que cai. O «Guardar» grava no `maquina.json` pelo `machine.declare` que já existe
# (`acionadores`, `utils/maquina.AcionadorDeclarado`); o daemon acha o aparelho pelo `/sys` e
# soma a tecla ao pad virtual (`daemon/subsystems/gamepad.PonteDosAcionadores`).

TIPO_ENTRADA = "entrada"
#: o que não fala pelo ar e só ocupa a porta: sem «⋮», sem mover e fora da régua do ar.
SO_OCUPA_A_PORTA = frozenset({"webcam", TIPO_ENTRADA})
USAR_COMO_BOTOES = "Usar como botões de…"
DICA_DO_USAR_COMO = "As teclas dele viram botões de um controle"
ACIONADOR_SEM_NOME = "Acionador USB"
TITULO_DO_ACIONADOR = "{nome} · usar como botões de"
DICA_DO_ACIONADOR = "Aperte uma tecla do acionador e clique no botão do controle onde ela cai"
ESPERAR_A_TECLA = "Esperar a próxima tecla"
ROTULO_DA_TECLA = "Tecla {n}"
#: quanto tempo o «Esperar a próxima tecla» espera, em segundos, numa thread (nunca no tique).
ESPERA_DA_TECLA_S = 10.0
_BRILHO_DO_DESTINO = "{{filter:drop-shadow(0 0 1.2px #bd93f9) drop-shadow(0 0 2.4px #bd93f9)}}"
_CODIGO_DE_TECLA = re.compile(r"^[0-9]{1,3}$")
_CHAVE_DE_CONTROLE = re.compile(r"^[0-9a-f]{12}$")


def _botoes_do_desenho() -> tuple[tuple[str, str, str], ...]:
    """``(peça do desenho, botão do pad, nome na tela)`` dos botões que a troca conhece.

    O dono é a aba Mapa do controle (`a13_mapa_do_controle.BOTOES_DA_PAGINA`): a mesma peça do
    mesmo desenho, com o mesmo nome. O PS, o microfone e o touchpad ficam de fora, como lá.
    """
    from hefesto_dualsense4unix.core.remapeamento_de_botao import REMAPEAVEIS

    from . import a13_mapa_do_controle as a13

    vistos: dict[str, tuple[str, str, str]] = {}
    for b in a13.BOTOES_DA_PAGINA:
        if b.motor in REMAPEAVEIS and b.peca not in vistos:
            vistos[b.peca] = (b.peca, b.motor, b.nome.removesuffix(" clique"))
    return tuple(vistos.values())


def peca_do_botao(botao: str) -> str:
    return next((peca for peca, motor, _ in _botoes_do_desenho() if motor == botao), botao)


def botao_da_peca(peca: str) -> str | None:
    return next((motor for p, motor, _ in _botoes_do_desenho() if p == peca), None)


def nome_do_botao(botao: str | None) -> str:
    return next((nome for _, motor, nome in _botoes_do_desenho() if motor == botao),
                TRACO_CURTO)


@_dataclasses.dataclass
class _Rascunho:
    """O que a janela do acionador mostra: o aparelho, o controle e as teclas, até o «Guardar»."""

    alvo: str
    chave: str
    nome: str
    controle: str
    #: ``[código evdev, rótulo, botão do pad ou None]``, na ordem em que a tecla chegou
    teclas: list[list[Any]] = _dataclasses.field(default_factory=list)
    sel: int | None = None
    esperando: bool = False


_RASCUNHO: _Rascunho | None = None
_TRAVA_DO_RASCUNHO = threading.Lock()


def _rascunho_da_linha(ap: dict[str, Any], quem: list[tuple[str, str]]) -> _Rascunho:
    teclas = [[int(c), str(r), b] for c, r, b in ap.get("teclas") or ()]
    controle = str(ap.get("controle") or "") or (quem[0][0] if quem else "")
    return _Rascunho(alvo=str(ap["id"]), chave=str(ap.get("chave") or ""),
                     nome=str(ap.get("nome") or ap.get("rotulo") or ACIONADOR_SEM_NOME),
                     controle=controle, teclas=teclas,
                     sel=teclas[0][0] if teclas else None)


def _acionadores_da_cena(cena: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in cena.get("aparelhos", ()) if a.get("tipo") == TIPO_ENTRADA]


def _rascunho_na_tela(cena: dict[str, Any]) -> _Rascunho | None:
    """O rascunho armado, se o aparelho dele está na tela; senão, o primeiro acionador dela."""
    linhas = _acionadores_da_cena(cena)
    r = _RASCUNHO
    if r is not None and any(str(a["id"]) == r.alvo for a in linhas):
        return r
    return _rascunho_da_linha(linhas[0], _quem_recebe(cena)) if linhas else None


def _quem_recebe(cena: dict[str, Any]) -> list[tuple[str, str]]:
    """``(chave do controle, nome do plástico)`` de quem pode receber as teclas."""
    return [(str(k), str(n)) for k, n in cena.get("quem_recebe") or ()]


def html_das_teclas(r: _Rascunho | None) -> str:
    if r is None:
        return ""
    return "".join(
        f'<label class="ac-tecla{" sel" if codigo == r.sel else ""}">'
        f'<input type="radio" name="ac-t" value="{codigo}" data-linha="tecla"'
        f'{" checked" if codigo == r.sel else ""}>'
        f'<span class="ac-de">{_x(rotulo)}</span><span class="ac-seta">→</span>'
        f'<span class="ac-para">{_x(nome_do_botao(botao))}</span></label>'
        for codigo, rotulo, botao in r.teclas)


def html_de_quem_recebe(r: _Rascunho | None, quem: list[tuple[str, str]]) -> str:
    escolhido = r.controle if r is not None else ""
    return "".join(
        f'<option value="{_x(chave)}"{" selected" if chave == escolhido else ""}>{_x(nome)}'
        '</option>' for chave, nome in quem)


def css_do_brilho(r: _Rascunho | None) -> str:
    """Os botões do desenho que já recebem uma tecla acendem (o roxo do desenho aprovado)."""
    pecas = [] if r is None else list(dict.fromkeys(
        peca_do_botao(str(b)) for _, _, b in r.teclas if b))
    if not pecas:
        return ""
    return (",".join(f"#acionador #ac-{p}" for p in pecas)
            + _BRILHO_DO_DESTINO.format())


def campos_do_acionador(cena: dict[str, Any]) -> dict[str, Any]:
    r = _rascunho_na_tela(cena)
    return {
        "acionador-titulo": TITULO_DO_ACIONADOR.format(
            nome=r.nome if r is not None else ACIONADOR_SEM_NOME),
        "acionador-quem": html_de_quem_recebe(r, _quem_recebe(cena)),
        "acionador-teclas": html_das_teclas(r),
        "acionador-brilho": css_do_brilho(r),
        # O desenho veste o plástico do controle escolhido (`data-colorway`, a folha da página).
        "acionador-desenho": (cena.get("colorway_de") or {}).get(r.controle, "") if r else "",
    }


def html_do_acionador(cena: dict[str, Any], desenho: str) -> str:
    """A janela «Usar como botões de»; o miolo vivo são os quatro campos do acionador."""
    c = campos_do_acionador(cena)
    alvo = _x(next((str(a["id"]) for a in _acionadores_da_cena(cena)), ""))
    return (
        '<div class="tela-nova" id="acionador">'
        '<div class="tn-cx ac-cx" role="dialog" aria-modal="true" '
        'aria-label="Usar o acionador como botões">'
        f'<div class="tn-topo"><span class="tn-tit" data-campo="acionador-titulo">'
        f'{_x(c["acionador-titulo"])}</span>'
        '<select class="ac-quem" aria-label="De qual controle" data-campo="acionador-quem" '
        f'data-hef-alvo="html">{c["acionador-quem"]}</select>'
        '<a class="tn-x" href="#" data-dica="Fechar">\u00d7</a></div>'
        '<div class="tn-corpo ac-corpo">'
        f'<div class="ac-lista"><div class="ac-dica">{DICA_DO_ACIONADOR}</div>'
        '<div class="ac-teclas" data-campo="acionador-teclas" data-hef-alvo="html">'
        f'{c["acionador-teclas"]}</div>'
        f'<button class="btn ac-mais" data-gesto="acionador-nova-tecla" data-alvo="{alvo}">'
        f'{ESPERAR_A_TECLA}</button></div>'
        f'<div class="ac-desenho">{desenho}</div></div>'
        '<div class="tn-rod"><a class="btn" href="#">Cancelar</a>'
        f'<a class="btn roxo" href="#" data-gesto="acionador-guardar" data-hef-forma="acionador" '
        f'data-alvo="{alvo}">Guardar</a></div>'
        '<style data-campo="acionador-brilho" data-hef-alvo="html">'
        f'{c["acionador-brilho"]}</style>'
        '</div></div>')


def _os_acionadores_declarados(declaracao: Any, lugares: list[dict[str, Any]]
                               ) -> list[dict[str, Any]]:
    """A linha de cada acionador do `maquina.json`, no primeiro adaptador (como no desenho)."""
    declarados = getattr(declaracao, "acionadores", None)
    if not lugares or not isinstance(declarados, dict):
        return []
    linhas = []
    for chave, a in declarados.items():
        teclas = getattr(a, "teclas", None) or {}
        linhas.append({
            "id": chave, "chave": chave, "tipo": TIPO_ENTRADA, "lugar": lugares[0]["id"],
            "nome": str(getattr(a, "nome", None) or ""), "rotulo": ACIONADOR_SEM_NOME,
            "controle": str(getattr(a, "controle", None) or ""), "fixo": True,
            "esperando": False,
            "teclas": [(int(c), ROTULO_DA_TECLA.format(n=n), b)
                       for n, (c, b) in enumerate(teclas.items(), 1)]})
    return linhas


def _quem_recebe_da_mesa(ctx: Contexto, declaracao: Any) -> list[tuple[str, str]]:
    """Os controles na mesa, pelo plástico; o que o acionador já declarou entra mesmo fora dela."""
    quem: list[tuple[str, str]] = []
    for m in ctx.mesa:
        chave = _so_hex(str(m.get("uniq") or "")).lower()
        nome = str(m.get("nome") or "")
        if _CHAVE_DE_CONTROLE.match(chave) and all(k != chave for k, _ in quem):
            quem.append((chave, nome if nome and nome != _cor_desconhecida() else "DualSense"))
    for a in (getattr(declaracao, "acionadores", None) or {}).values():
        chave = str(getattr(a, "controle", None) or "")
        if chave and all(k != chave for k, _ in quem):
            quem.append((chave, _cor_declarada_de(chave) or "DualSense"))
    return quem


def _colorways_da_mesa(ctx: Contexto) -> dict[str, str]:
    """O modelo do mapa dela de cada controle na mesa (`""` quando ninguém leu)."""
    return {_so_hex(str(m.get("uniq") or "")).lower(): colorway_do_controle(m) for m in ctx.mesa}


#: Onde a espera da tecla acha e abre o aparelho; a régua troca os dois por dublês.
_RAIZ_DAS_ENTRADAS: Any = None


_ABRIR_O_EVENTO: Callable[[str], Any] | None = None


def _evento_do_acionador(chave: str) -> str | None:
    from hefesto_dualsense4unix.utils.maquina import aparelhos_de_entrada

    return next((a.evento for a in aparelhos_de_entrada(_RAIZ_DAS_ENTRADAS) if a.chave == chave),
                None)


def _esperar_a_tecla(r: _Rascunho, evento: str, prazo_s: float = ESPERA_DA_TECLA_S) -> None:
    """Abre o aparelho só para ler (sem prender) e guarda a primeira tecla apertada."""
    from hefesto_dualsense4unix.utils.maquina import abrir_o_aparelho_de_entrada

    dispositivo = None
    try:
        dispositivo = (_ABRIR_O_EVENTO or abrir_o_aparelho_de_entrada)(evento)
        fim = time.monotonic() + prazo_s
        # O `select` dorme no nó até ele ter evento ou o prazo vencer: nenhuma volta em vão.
        while (restante := fim - time.monotonic()) > 0:
            if not select.select([dispositivo.fd], [], [], restante)[0]:
                return
            ev = dispositivo.read_one()
            if ev is None:
                continue
            if getattr(ev, "type", None) == 1 and getattr(ev, "value", None) == 1:
                codigo = int(ev.code)
                with _TRAVA_DO_RASCUNHO:
                    if all(t[0] != codigo for t in r.teclas):
                        r.teclas.append([codigo, ROTULO_DA_TECLA.format(n=len(r.teclas) + 1),
                                         None])
                    r.sel = codigo
                return
    except Exception as exc:
        print(f"[08] a espera da tecla do acionador caiu: {exc}", file=sys.stderr, flush=True)
    finally:
        r.esperando = False
        if dispositivo is not None:
            with contextlib.suppress(OSError):
                dispositivo.close()


def _o_rascunho() -> _Rascunho:
    r = _rascunho_na_tela(_CENA_NA_TELA)
    if r is None:
        raise ValueError("acionador: nenhum aparelho de entrada está na tela")
    return r


#: ``054C``): o DualSense e o Edge seguram PS + Create; o DualShock 4, PS +
BOTOES_DE_PAREAR = {"0ce6": "PS + Create", "0df2": "PS + Create",
                    "05c4": "PS + Share", "09cc": "PS + Share"}
ICONE_DO_CUSTO = {"mic": "mic", "som": "som", "haptica": "vibra"}
NOME_DO_CUSTO = {"mic": "microfone", "som": "som", "haptica": "vibração"}
#: A cor de cada tipo na sala é o NOME do token (``--sala-<tipo>``), nunca o hex: o valor mora na
#: raiz da folha da aba (`aba08.CORES_NA_SALA`), e é ali que um tema de cores o troca.
COR_DO_TIPO = {
    tipo: f"var(--sala-{tipo})"
    for tipo in ("teclado", "mouse", "webcam", "caixa", "fone", "outro", "celular", "relogio",
                 "gamepad")
}
COR_DO_TIPO[TIPO_ACESSORIO] = CATEGORIA_ACESSORIO["cor"]
#: o aparelho de entrada (o acionador) leva a cor da webcam, como no desenho aprovado (r3-08-14)
COR_DO_TIPO["entrada"] = COR_DO_TIPO["webcam"]
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
    """O DualSense na cor do plástico, pelo `color` (o sprite é `currentColor`).

    Sem o `data-colorway` do desenho: a folha das zonas (`svg[data-colorway] .z-casca`) não alcança
    o que mora atrás de um `<use>` (o seletor casa o SÍMBOLO no sprite, que aqui nem tem classes de
    zona), o atributo seria cor cravada sem efeito e o portão da cor
    (`check_a_cor_vem_do_aparelho.py`) o acusa.
    """
    cor = ap.get("cor") or "var(--texto-mudo)"
    return (f'<svg class="i {classe}" aria-hidden="true" style="color:{_x(cor)}">'
            f'<use href="#rd-ds"/></svg>')


def _maiuscula(frase: str) -> str:
    return frase[:1].upper() + frase[1:]


def _cor_de(ap: dict[str, Any]) -> str:
    return str(ap.get("cor") or COR_DO_TIPO.get(str(ap.get("tipo")), "var(--texto-mudo)"))


def _veu(cor: str, alfa: float) -> str:
    """A cor com transparência: o hex do plástico vira `rgba`, e o token da sala se mistura
    com o transparente no próprio motor, sem que o Python saiba o valor que o tema pôs."""
    if (cor or "").startswith("var("):
        return f"color-mix(in srgb, {cor} {round(alfa * 100)}%, transparent)"
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

    Cada tipo diz o próprio gesto, ou não pede o que não sabe (25/09, passo c3: mover um TECLADO
    pedia «segure PS + Create» e mostrava o DualSense). O controle que o daemon publica é DualSense;
    sem ``Modalias`` é ele, com ``Modalias`` vale o modelo (:data:`BOTOES_DE_PAREAR`). Teclado, fone
    ou controle de outra marca não têm gesto conhecido e a linha não inventa um.
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


def _hz_da_ponte(ap: dict[str, Any]) -> str:
    """A taxa que a ponte escreve AGORA: vazio quando ela cede (pela fila ou pelo sinal) ou
    sem medida (o piloto põe o travessão); `HZ_DA_PONTE` é só o alvo de projeto, do desenho."""
    if "hz_ponte" not in ap:  # o desenho: sem governador, a taxa de projeto
        return _hz(HZ_DA_PONTE)
    if ap.get("ponte_pausada") or ap.get("ponte_cedendo"):
        return ""
    return _hz(ap.get("hz_ponte"))


#: A última vez em que a ponte de cada controle foi vista cedendo (pela fila ou pelo sinal).
_PONTE_CEDEU_EM: dict[str, float] = {}


def _hz_da_ponte_seguro(ap: dict[str, Any], agora: float) -> str:
    """:func:`_hz_da_ponte` que PIORA NA HORA E MELHORA DEVAGAR, como a cor (`_nivel_seguro`).

    O rodízio da fila troca quem cede a cada janela de 0,25 s: lida pelo ``state_full``, a
    ponte alternaria «62 Hz» e vazio, e a caixa piscaria. Cedeu, a caixa esvazia na hora; o
    número só volta depois de :data:`SEGURA_O_NIVEL_S` sem ceder.
    """
    uid = str(ap.get("id"))
    texto = _hz_da_ponte(ap)
    if "hz_ponte" not in ap:
        return texto
    if ap.get("ponte_pausada") or ap.get("ponte_cedendo"):
        _PONTE_CEDEU_EM[uid] = agora
        return ""
    cedeu = _PONTE_CEDEU_EM.get(uid)
    if cedeu is not None and agora - cedeu < SEGURA_O_NIVEL_S:
        return ""
    _PONTE_CEDEU_EM.pop(uid, None)
    return texto


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
        hz = (f'<span class="hz" data-campo="hz-ponte" data-alvo="{aid}">'
              f'{_x(_hz_da_ponte(ap)) if com_hz else ""}</span>') if ligado else ""
        passou = " Passou do limite: pode engasgar." if (ligado and alem) else ""
        rotulo = _maiuscula(NOME_DO_CUSTO[k])
        botoes_da_ponte.append(
            f'<span class="vaga {k}{" alem" if ligado and alem else ""}" role="img" '
            f'{"data-ligada " if ligado else ""}'
            f'aria-label="{rotulo} de {nome}: {"ligado" if ligado else "desligado"}" '
            f'title="{rotulo}: até {round(HZ_DA_PONTE)} por segundo. Pelo BT, som ou '
            f'vibração, um por vez.{passou}" style="flex:{flex}" '
            f'data-alvo="{aid}">{_ic(ICONE_DO_CUSTO[k])}{hz}</span>')
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
        f'<span class="selo-zero" role="img" {"data-ligada " if ap.get("luz", True) else ""}'
        f'aria-label="Barra de luz de {nome}: {"ligada" if ap.get("luz", True) else "desligada"}" '
        f'title="Barra de luz: não pesa no rádio" data-alvo="{aid}">{_ic("lightbar")}</span>'
        '</div></div>')


def _vaga_de(ap: dict[str, Any], cena: dict[str, Any]) -> int:
    if ap.get("tipo") != "controle" or not ap.get("ponte"):
        return 0
    pontes = _pontes(cena, str(ap.get("lugar")))
    return pontes.index(ap) + 1 if ap in pontes else 0


def _tem_menu(ap: dict[str, Any]) -> bool:
    """Toda linha tem o «⋮» (desenho aprovado de 05/10/2026), menos a que espera o gesto."""
    return not ap.get("esperando") and ap.get("tipo") not in SO_OCUPA_A_PORTA


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
    dica = f"Opções de {nome} neste adaptador" if nome else "Opções deste aparelho neste adaptador"
    return (f'<button class="menu-da-linha" title="{_x(dica)}" aria-label="{_x(dica)}" '
            f'aria-haspopup="true" data-gesto="aparelho-menu" data-alvo="{_x(ap["id"])}" '
            f'data-lugar="{_x(ap.get("lugar") or "")}">'
            f'<span aria-hidden="true">{MENU_DA_LINHA}</span></button>')


def html_da_linha(ap: dict[str, Any], cena: dict[str, Any], com_hz: bool = False) -> str:
    """Uma linha da sala: desenho, nome, o que manda e recebe, qual vaga de ponte."""
    aid = _x(ap["id"])
    esperando = bool(ap.get("esperando"))
    arrasta = not ap.get("fixo") and not esperando and ap.get("tipo") not in SO_OCUPA_A_PORTA
    nome = str(ap.get("nome") or "")
    rotulo = str(ap.get("rotulo") or "")
    tipo = str(ap.get("tipo"))
    quem = "controle" if tipo == "controle" else PALAVRA_DO_TIPO.get(tipo, tipo)
    le = _x(f"{nome_na_conexoes(ap) or rotulo}, {quem}")
    if arrasta:
        abre = (f'<div class="linha" data-id="{aid}" data-alvo="{aid}" draggable="true" '
                f'tabindex="0" role="button" aria-label="{le} — Enter para mudar de adaptador">')
    else:
        estado = (" esperando" if esperando else " nao-conectou" if ap.get("nao_conectou")
                  else " desligado" if ap.get("desligado") else "")
        r3 = ' data-r3="14"' if tipo == TIPO_ENTRADA else ""
        abre = (f'<div class="linha{estado}" data-id="{aid}" '
                f'data-alvo="{aid}"{r3} aria-label="{le}">')
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
    elif ap.get("tipo") in SO_OCUPA_A_PORTA:
        usar = (f'<a class="btn usar-como" href="#acionador" data-gesto="usar-como-botoes" '
                f'data-alvo="{aid}" title="{DICA_DO_USAR_COMO}">{USAR_COMO_BOTOES}</a>'
                if ap.get("tipo") == TIPO_ENTRADA else "")
        return (abre + desenho + campo + f'<div class="features"><span class="sem-radio" '
                f'title="Não usa rádio; só ocupa porta">{SEM_RADIO}</span>{usar}</div>'
                '<span class="conta-da-vaga zero" title="Não usa rádio">'
                + TRACO_CURTO + '</span></div>')
    elif ap.get("tipo") == "outro" and not ap.get("tipo_dela"):
        return _linha_sem_tipo(ap, abre, le, nome, rotulo, aid)
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


def _linha_sem_tipo(ap: dict[str, Any], abre: str, le: str, nome: str, rotulo: str,
                    aid: str) -> str:
    """O aparelho do Bluetooth que nem o ``Icon``, nem a ``Class``, nem a ``Appearance`` nomeiam.

    No lugar do ícone vai o «?» (desenho do todo, 13/10/2026): clicar abre a grade «O que é este
    aparelho?», e a escolha, guardada pelo endereço, vence a adivinhação. Sem rádio de som, a conta
    da vaga é o traço.
    """
    quem = _x(f"{nome or 'Aparelho'}, sem tipo")
    abre = abre.replace(f'aria-label="{le}', f'aria-label="{quem}', 1)
    pergunta = (f'<a class="tipo-qual" href="#tipo-do-aparelho" data-alvo="{aid}" '
                'title="O que é este aparelho? Clique e escolha">?</a>')
    campo = (f'<input class="nome" value="{_x(nome)}" placeholder="{_x(rotulo or SEM_NOME)}" '
             'aria-label="Nome deste aparelho" title="Clique para renomear; arraste para mover" '
             f'draggable="true" data-gesto="aparelho-renomear" data-alvo="{aid}">')
    return (abre + pergunta + campo + f'<div class="features"><span class="sem-radio" '
            f'title="{SEM_TIPO_DICA}">{SEM_TIPO}</span></div>'
            '<span class="conta-da-vaga zero" title="Não leva som">' + TRACO_CURTO + '</span>'
            + _o_menu(ap) + '</div>')


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
                      f'data-alvo="{_x(lug.get("lugar") or "")}" title="Mapear entrada a entrada">'
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


NADA_NO_ADAPTADOR = "Nenhum aparelho neste adaptador"


def html_do_lugar(lug: dict[str, Any], cena: dict[str, Any], com_hz: bool = False) -> str:
    """O cartão de um adaptador: a linha de cima, e os aparelhos quando aberto."""
    lid = _x(lug["id"])
    pontes = _pontes(cena, str(lug["id"]))
    moradores = _moradores(cena, str(lug["id"]))
    ocupado = _ocupado(cena)
    apagado = (f'{" apagado" if ocupado else ""}" aria-disabled="{str(ocupado).lower()}" '
               'data-campo="radio-ocupado" data-hef-alvo="classe" data-hef-classe="apagado" '
               'data-hef-atributo="aria-disabled')
    lampada = ""
    if cena.get("proposta") and cena["proposta"].get("destino") == lug["id"]:
        lampada = (f'<button class="lampada{apagado}" title="Quem funciona melhor aqui" '
                   f'aria-label="Quem funciona melhor aqui" data-gesto="sugerir-alocacao" '
                   f'data-alvo="{lid}">{_ic("lampada")}</button>')
    # O adaptador sem nada dentro não abre (19/10/2026, a foto da aba Conexões): a seta fica
    # apagada e o corpo vazio não ocupa a linha. O escolhido para o Conectar abre mesmo vazio:
    # é nele que o aparelho novo vai chegar.
    vazio = (not moradores and not lampada
             and cena.get("destino_do_conectar") != lug["id"])
    aberto = cena.get("aberto") == lug["id"] and not vazio
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
    if vazio:
        ver = NADA_NO_ADAPTADOR
    seta = "" if unica else (
        f'<button class="abre-lugar" aria-expanded="{str(aberto).lower()}" title="{ver}" '
        f'aria-label="{ver}" data-gesto="abrir-adaptador" data-alvo="{lid}"'
        f'{" disabled" if vazio else ""}><span aria-hidden="true">▶</span></button>')
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
        if ap.get("fixo") or ap.get("esperando") or ap.get("tipo") in SO_OCUPA_A_PORTA:
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
    """O menu «⋮» de cada linha que tem pareamento ali, e a pergunta do «Esquecer» dele.

    O menu é um painel (``data-painel="menu"``, pelo par ``linha|adaptador``) com o «Esquecer», como
    o «⋮» das Configurações do COSMIC (foto 8 dela), sem «Desconectar» (R7: o desconectar mora no
    mover) e sem «Renomear» (é o campo do nome). O «sim» é ``confirmar-esquecer`` e o endereço é
    ``(linha, adaptador)``: ``data-esquecer`` separa estas das perguntas de mover, de mesma forma.
    """
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
                      + _estado_na_gaveta(ap, lug)
                      + (f'<p class="explica">{ESQUECER_FAZ}</p>' if esquece else "")
                      + _botoes(itens, "btn apaga") + '</template>')
        if not esquece:
            continue
        moldes.append(f'<template class="pergunta-molde" data-esquecer="1" '
                      f'data-alvo="{alvo}" data-destino="{lid}" '
                      f'data-sim="{ESQUECER}" data-gesto="confirmar-esquecer">'
                      f'{pergunta_de_esquecer(ap, lug)}</template>')
    return "".join(moldes)


def _botoes(itens: list[tuple[str, str, str]], classe: str = "btn") -> str:
    """`(ícone, rótulo, atributos)` → a lista de botões de um painel."""
    return ('<div class="escolha">' + "".join(
        f'<button class="{classe}" {attrs}>{_ic(ic) if ic else ""}{_x(rot)}</button>'
        for ic, rot, attrs in itens) + "</div>")


def _estado_na_gaveta(ap: dict[str, Any], lug: dict[str, Any]) -> str:
    """O estado do aparelho na gaveta do «⋮», embaixo do nome: o que a linha diz · o adaptador."""
    if ap.get("nao_conectou"):
        estado = f'<span class="nao-conectou">{NAO_CONECTOU}</span>'
    elif ap.get("desligado"):
        estado = _x(USB if ap.get("usb") else DESLIGADO)
    else:
        estado = CONECTADO
    onde = _titulo_do_lugar(lug)
    return f'<p class="estado">{estado}{" · " + _x(onde) if onde else ""}</p>'


def _moldes_de_painel(cena: dict[str, Any]) -> str:
    lugares = list(cena.get("lugares", ()))
    moldes = []
    movidos = [a for a in cena.get("aparelhos", ())
               if not a.get("fixo") and not a.get("esperando")
               and a.get("tipo") not in SO_OCUPA_A_PORTA]
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
    pelo_sinal = ' data-pelo-sinal="sim"' if proposta.get("pelo_sinal") else ""
    return (f'<template class="balao-molde" data-controle="{_x(ap["id"])}" '
            f'data-destino="{_x(destino["id"])}"><div class="balao" '
            f'data-destino="{_x(destino["id"])}"{pelo_sinal}>{_ic("lampada")}{desenho}'
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
    "celular", "relogio", TIPO_ACESSORIO, "fone", "caixa", "teclado", "mouse", "wifi", "ruido"})
#: A legenda do título: quem é o tipo e como ele se chama na tela.
LEGENDA_DAS_FAIXAS = (
    ("controle", "Controles"), ("celular", "Celular"), ("relogio", "Relógio"),
    (TIPO_ACESSORIO, CATEGORIA_ACESSORIO["legenda"]),
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
                          if a.get("tipo") not in SO_OCUPA_A_PORTA and _no_ar(a))
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
        saida[nome_do_jogador.mac(fim) or str(fim)] = (
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


def _o_canal_le(c: Any) -> str:
    """A célula de um canal de baixa energia: o canal LE e a frequência dele, «não medido»."""
    k = faixas_do_ar.canal_le_da_celula(c.canal)
    anuncio = c.estado == faixas_do_ar.ANUNCIO
    classe = "n a" if anuncio else "n"
    sobre = "anúncio, não medido" if anuncio else "não medido"
    return f'<i class="{classe}" title="Canal LE {k} · {2402 + 2 * k} MHz · {sobre}"></i>'


def _o_canal(c: Any, cores: dict[str, str], nomes: dict[str, str]) -> str:
    if c.estado in (faixas_do_ar.NAO_MEDIDO, faixas_do_ar.ANUNCIO):
        return _o_canal_le(c)
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
#: A medida da faixa lê o mapa de canais que o adaptador evita, e esse mapa só existe com algum
#: aparelho conectado pelo Bluetooth (não só o controle). Por isso a frase pede o aparelho
#: (08/10/2026).
FAIXA_NAO_ENCONTRADA = "Precisa de um aparelho no Bluetooth"
FAIXA_NAO_ACHADA = (
    f"{FAIXA_NAO_ENCONTRADA} · A faixa se mede pelo mapa de canais que o adaptador evita, e esse "
    "mapa só existe com algum aparelho conectado pelo Bluetooth, não só o controle. Clique para "
    "tentar de novo.")
#: o rótulo do botão que a faixa vazia do receptor vira (desenho de 06/10/2026, item 1): o gesto
#: mora à vista, no lugar dos canais que faltam, e não num ponto de 10 px explicado só no tooltip.
DESCOBRIR_A_FAIXA = "Descobrir a faixa"
#: O que a faixa de um enlace de baixa energia diz ao leitor de tela (a opção 1 do usuário, de
#: 09/10/2026: os 40 canais LE, «não medido», e os três de anúncio marcados).
LE_NAO_MEDIDO = f"{faixas_do_ar.CANAIS_LE} canais de baixa energia, não medidos"
TENTAR_DE_NOVO = f"{FAIXA_NAO_ENCONTRADA} · Tentar de novo"


def _o_ponto(linha: Any) -> str:
    """O estado da linha num ponto: verde = bom, laranja ou vermelho = problema, vazado = sem selo.

    O texto do problema («3 teclas presas em 1 h») vai só no tooltip; o verde diz «Tudo certo».
    Para o leitor de tela o ponto diz a palavra inteira («Boa 74/79»): a cor nunca vai sozinha.
    O ponto é sempre o estado (no receptor, as falhas lidas); o «Descobrir» mora na faixa
    (desenho de 06/10/2026: o vazado que era botão escondia o «sem falhas» do mouse e do teclado).
    """
    selo = linha.selo
    ruim = selo is not None and selo.nivel != "boa"
    nivel = _x(str(selo.nivel).replace(" ", "-")) if selo is not None else ""
    junta = " " if linha.nota.startswith("em ") else " · "
    dito = (_maiuscula(junta.join(t for t in (selo.texto, linha.nota) if t)) if selo is not None
            else _maiuscula(linha.sem_faixa))
    # o que se leu do enlace continua no tooltip, depois do estado
    ja_dito = selo is not None and "tira canais" in selo.texto
    so_o_sinal = selo is not None and selo.nivel == faixas_do_ar.SINAL
    extras = [t for t in (
        f"sinal {linha.rssi} dBm" if isinstance(linha.rssi, int) and not so_o_sinal else "",
        (f"qualidade do enlace {linha.qualidade_do_enlace}/255"
         if isinstance(linha.qualidade_do_enlace, int) else ""),
        f"tira canais de {linha.tira_de}" if linha.tira_de and not ja_dito else "",
        linha.dica) if t]
    dica = " · ".join([TUDO_CERTO if selo is not None and not ruim else dito, *extras])
    fala = " · ".join([dito, *extras])
    classe = nivel if selo is not None else "sem"
    return (f'<span class="ar-selo {classe}" role="img" title="{_x(dica)}" '
            f'aria-label="{_x(fala)}"></span>')


def _e_fora_da_faixa(linha: Any) -> bool:
    """A linha que não divide a faixa dos controles (o Wi-Fi em 5 GHz): não tem célula nenhuma."""
    return not linha.celulas and linha.sem_faixa == faixas_do_ar.FORA_DA_FAIXA


def _o_fora_no_titulo(linha: Any) -> str:
    """O selo «Wi-Fi · 5 GHz · canal 161 ●» que mora no título «Outros dispositivos sem fio».

    Escondido de saída: a página o mostra no lugar da linha só quando a seção não cabe no miolo
    (``oQueEstaForaDaFaixaCabe``, desenho de 06/10/2026, pergunta 1, opção A). O ponto é o mesmo
    da linha, e o texto é o que a linha diz.
    """
    texto = " · ".join(t for t in (linha.nome, linha.sub) if t)
    return (f'<span class="ar-no-titulo" data-linha="{_x(linha.id)}">{_x(texto)}'
            f'{_o_ponto(linha)}</span>')


def _a_linha_do_ar(linha: Any, rot: str, cores: dict[str, str], nomes: dict[str, str]) -> str:
    cor = cores[linha.id]
    nada = _passo_da_linha(linha.id) == receptor_sem_fio.PASSO_NADA
    if linha.celulas:
        le = linha.sem_faixa == faixas_do_ar.DIVIDE_O_RADIO
        resumo = (f"{nomes[linha.id]}: {linha.bons} dos {CANAIS_DO_BT} canais bons"
                  if linha.bons is not None
                  else f"{nomes[linha.id]}: {LE_NAO_MEDIDO}" if le
                  else f"{nomes[linha.id]}: faixa ocupada")
        classe = "ar-faixa le" if le else "ar-faixa"
        faixa = (f'<div class="{classe}" role="img" aria-label="{_x(resumo)}">'
                 + "".join(_o_canal(c, cores, nomes) for c in linha.celulas) + "</div>")
    elif linha.sem_faixa == faixas_do_ar.FORA_DA_FAIXA:
        # o Wi-Fi em 5 GHz: a linha fica, e o trilho diz onde ele está (desenho de 06/10/2026)
        faixa = (f'<div class="ar-faixa fora" role="img" title="{_x(linha.sem_faixa)}" '
                 f'aria-label="{_x(f"{linha.sub}: {linha.sem_faixa}")}">'
                 f'<span>{_x(linha.sub)}</span></div>')
    else:
        frase, descobrir = _o_botao_da_descoberta(linha)
        if descobrir:
            # a faixa por descobrir É o botão «Descobrir a faixa», à vista (desenho de 06/10/2026)
            dica = FAIXA_NAO_ACHADA if nada else FAIXA_NAO_DESCOBERTA
            rotulo = TENTAR_DE_NOVO if nada else DESCOBRIR_A_FAIXA
            # o nome que o leitor de tela e o comando de voz ouvem CONTÉM o rótulo à vista
            # (WCAG 2.5.3): quem diz «Descobrir a faixa» acha o botão; o porquê fica no title
            faixa = (f'<button class="ar-faixa sem descobrir" type="button" '
                     f'data-gesto="receptor-descobrir" data-alvo="{_x(linha.id)}" '
                     f'title="{_x(dica)}" aria-label="{_x(f"{rotulo} · {nomes[linha.id]}")}">'
                     f'<span>{rotulo}</span></button>')
        else:
            # o passo do gesto guiado («Tire o receptor da porta») é a única frase que a faixa diz
            passo = f"<span>{_x(frase)}</span>" if frase else ""
            faixa = (f'<div class="ar-faixa sem" role="img" '
                     f'aria-label="{_x(frase or linha.sem_faixa)}">{passo}</div>')
    donos = " ".join(dict.fromkeys(t for t, _n in linha.quem))
    fora = " data-fora-da-faixa" if _e_fora_da_faixa(linha) else ""
    return (f'<div class="ar-linha" data-id="{_x(linha.id)}" data-tipo="{_x(linha.tipo)}" '
            f'data-briga="{_x(" ".join(linha.briga))}" data-quem="{_x(donos)}" tabindex="0" '
            f'style="--cor:{_x(cor)}"{fora}>{rot}{faixa}'
            f'<div class="ar-estado">{_o_ponto(linha)}</div></div>')


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
    no ar não ganha linha. O Wi-Fi conectado tem linha sempre, também em 5 GHz, com o trilho
    dizendo a banda e o canal (desenho de 06/10/2026, item 1); quando a seção não cabe no miolo,
    essa linha vira um selo no título do grupo (pergunta 1, opção A).
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
    outros = list(regua.outros)
    if outros:
        no_titulo = "".join(_o_fora_no_titulo(ln) for ln in outros if _e_fora_da_faixa(ln))
        saida.append(f'<div class="ar-grupo outros">{OUTROS_SEM_FIO}{no_titulo}</div>'
                     '<div class="ar-do">'
                     + "".join(_a_linha_do_ar(ln, rotulos[ln.id], cores, nomes) for ln in outros)
                     + "</div>")
    return '<div class="ar">' + "".join(saida) + "</div>"



#: O padrão de cada tipo na mini-faixa do painel do aparelho, que aparece na aba 08 e na página do
#: mapa das portas. Essa página não define token de tipo na raiz, então o padrão vai DENTRO do
#: ``var()``: sem tema, vale o hex; com um tema que defina ``--mapa-<tipo>``, vale o do tema.
PADRAO_DA_FAIXA_NO_MAPA = {
    "controle": "#f8f8f2", "celular": "#ff9a8b", "relogio": "#8fa8ff", "fone": "#8be9fd",
    "caixa": "#bd93f9", "teclado": "#ffb86c", "mouse": "#f1fa8c", "wifi": "#d4d7e0",
    "ruido": "#8a8fa3", "outro": "#9a9eb8", "adaptador": "#6272a4", TIPO_ACESSORIO: "#ff79c6",
}
COR_DA_FAIXA_NO_MAPA = {tipo: f"var(--mapa-{tipo},{cor})"
                        for tipo, cor in PADRAO_DA_FAIXA_NO_MAPA.items()}


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
        if a.get("ponte_pausada"):
            causa = CAUSA_LONGE_PAUSADA
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
        for saiu in set(_PONTE_CEDEU_EM) - {str(a["id"]) for a in controles}:
            del _PONTE_CEDEU_EM[saiu]
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
        "hz-ponte": [_hz_da_ponte_seguro(a, agora) if segurar else _hz_da_ponte(a)
                     for a in controles if a.get("ponte") in ("som", "haptica")],
        "espectro-canais": html_dos_canais(cena),
        "radio-ocupado": "sim" if _ocupado(cena) else "",
    }


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
        pousar(nome_do_jogador.mac(cheio), float(queda.carimbo), fato or "Os controles caíram")
    for linha in historico.get("diario") or ():
        o_que = str(linha.get("o_que") or "")
        carimbo = float(linha.get("carimbo") or 0.0)
        if o_que == "ponte subiu" and not linha.get("alem_do_limite"):
            continue
        if o_que in FRASE_DO_DIARIO:
            pousar(nome_do_jogador.mac(linha.get("adaptador")), carimbo, FRASE_DO_DIARIO[o_que])
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
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.gesto_de_pareamento import e_controle

    if e_controle(classe):
        # O controle que não é o DualSense (o Pro Controller, o 8BitDo, o do Xbox): a ``Class``
        # já diz que é controle, e a linha não pergunta à pessoa o que ele é.
        return "gamepad"
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


#: A categoria ``0x0F`` (HID) do GAP diz o aparelho pelos 6 bits de baixo, a subcategoria; o que não
#: está aqui (``0x03C0``, o HID genérico, e as outras) fica «outro», sem inventar.
_SUBCATEGORIA_HID = {0x01: "teclado", 0x02: "mouse", 0x03: "controle", 0x04: "controle"}


def _tipo_pela_aparencia(aparencia: int | None) -> str:
    """O tipo pela ``Appearance`` do GAP (a categoria são os 10 bits de cima): é o que um
    relógio, uma pulseira, um teclado ou um mouse LE tem quando o BlueZ não lhes dá ``Icon`` nem
    ``Class``."""
    if not isinstance(aparencia, int) or isinstance(aparencia, bool):
        return "outro"
    categoria = aparencia >> 6
    if categoria == 0x0F:
        return _SUBCATEGORIA_HID.get(aparencia & 0x3F, "outro")
    return {0x01: "celular", 0x03: "relogio"}.get(categoria, "outro")


def _tipo_do_aparelho(icone: str, classe: int | None, aparencia: int | None = None) -> str:
    """O tipo pelo ``Icon`` do BlueZ primeiro, depois pela classe e pela aparência."""
    pelo_icone = TIPO_PELO_ICONE.get(str(icone or ""))
    if pelo_icone:
        return pelo_icone
    pela_classe = _tipo_pela_classe(classe)
    return pela_classe if pela_classe != "outro" else _tipo_pela_aparencia(aparencia)


def _tipo_que_ela_disse(endereco: str) -> str:
    """O tipo que a pessoa deu a este aparelho do Bluetooth (``""`` quando não deu).

    Lido do ``maquina.json`` pelo ENDEREÇO: a escolha da pessoa vence a adivinhação do ``Icon``, da
    ``Class`` e da ``Appearance`` e sobrevive à releitura e ao reinício.
    """
    do_disco = getattr(_declaracao(), "aparelhos", None)
    dado = do_disco.get(_so_hex(endereco).lower()) if isinstance(do_disco, dict) else None
    tipo = str(getattr(dado, "tipo", "") or "")
    return TIPO_DA_LINHA_PELA_ESCOLHA.get(tipo, tipo)


def _com_a_categoria_do_enlace(aparelhos: list[dict[str, Any]],
                               enlaces: dict[str, dict[str, Any]]) -> None:
    """O aparelho conectado que não é controle, com enlace de baixa energia e sem tipo nos três
    leitores (``Icon``, ``Class``, ``Appearance``) é «Acessório».

    A regra é por fato, nunca por nome ou marca: o enlace LE vem do rádio (``radio_ar``, a chave
    ``enlaces``), e o tipo, do BlueZ. Ela mora aqui porque é o único lugar em que os dois se
    encontram (:func:`_tipo_do_aparelho` não vê o enlace).
    """
    for ap in aparelhos:
        if ap.get("tipo") != "outro" or ap.get("tipo_dela"):
            continue
        do_lugar = _dicionario(enlaces.get(str(ap.get("lugar") or "")))
        if _dicionario(do_lugar.get(_so_hex(str(ap.get("id") or "")))).get("le") is True:
            ap["tipo"] = TIPO_ACESSORIO


def _cor_declarada_de(aparelho: str) -> str:
    """O nome do plástico que a pessoa declarou para este aparelho, ou `""`."""
    try:
        from hefesto_dualsense4unix.integrations.cor_do_plastico import nome_do_aparelho
        from hefesto_dualsense4unix.interface import mesa_viva

        cor = mesa_viva.cor_declarada(_so_hex(aparelho), _declaracao())
        return nome_do_aparelho(cor) if cor is not None and cor.nome else ""
    except Exception:
        return ""


def _quem_pede_para_parear(central: dict[str, Any], lugares: list[dict[str, Any]],
                           aparelhos_bz: tuple[Any, ...]) -> list[dict[str, str]]:
    """Os controles conhecidos que pedem para parear (``radio_central.pedindo``), na tela.

    O dono do sinal é a central (conhecido + desconectado + ouvido na varredura); aqui só se
    dá o nome dela e o adaptador que o ouve. O nome de fábrica vira «Controle».
    """
    ids = {str(lug["id"]) for lug in lugares}
    nomes = nome_do_jogador.nomes_por_endereco(aparelhos_bz)
    saida = []
    for x in central.get("pedindo") or ():
        if not isinstance(x, dict):
            continue
        aparelho = nome_do_jogador.mac(x.get("aparelho"))
        lugar = nome_do_jogador.mac(x.get("adaptador"))
        if not aparelho or lugar not in ids:
            continue
        alias = str(x.get("nome") or "").strip()
        dado = nomes.get(aparelho) or (
            nome_do_jogador.nome_dado(alias)
            if alias and not nome_do_jogador.e_nome_de_fabrica(alias)
            and not nome_do_jogador.ALIAS_QUE_E_ENDERECO.fullmatch(alias) else "")
        saida.append({"aparelho": aparelho, "lugar": lugar,
                      "nome": dado or _cor_declarada_de(aparelho) or CONTROLE_SEM_NOME})
    return saida


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
    bluez = em_fundo.em_fundo("bluez", em_fundo.ler_o_bluez, 3.0)
    lida = em_fundo.em_fundo("maquina", _ler_a_maquina, 5.0)
    wifi = _o_wifi_com_as_quedas(em_fundo.em_fundo("wifi", _ler_o_wifi, 10.0) or [],
                                 em_fundo.em_fundo("wifi-quedas", _ler_as_quedas, 30.0))
    maquina, controladores = lida if lida else (None, {})
    if _DESCOBERTA.ativa:
        # o «Descobrir a faixa» anda pelo censo, e o censo da porta é lido uma vez e no
        # «Examinar»: com o gesto em curso ele se relê no fundo, senão o receptor tirado
        # continuaria «na porta» até o gesto se desfazer sozinho
        em_fundo.em_fundo("mesa-do-gesto", lambda: _mesa_do_radio(recarregar=True),
                  RELER_A_PORTA_NO_GESTO_S)
    mesa = _mesa_do_radio()
    adaptadores_bz, aparelhos_bz = bluez if bluez else ((), ())

    por_hci = {str(getattr(a, "interface", "")): a for a in getattr(mesa, "adaptadores", ()) or ()}
    enderecos: list[str] = []
    for a in adaptadores_bz:
        if nome_do_jogador.mac(a.endereco) and nome_do_jogador.mac(a.endereco) not in enderecos:
            enderecos.append(nome_do_jogador.mac(a.endereco))
    for chave in (*ar.keys(), *governador.keys()):
        if nome_do_jogador.mac(chave) and nome_do_jogador.mac(chave) not in enderecos:
            enderecos.append(nome_do_jogador.mac(chave))
    bz_de = {nome_do_jogador.mac(a.endereco): a for a in adaptadores_bz}

    agora = time.time()
    movimentos = [m for m in central.get("movimentos") or () if isinstance(m, dict)]
    busca = central.get("busca") if isinstance(central.get("busca"), dict) else None
    busca_em = nome_do_jogador.mac(busca.get("adaptador")) if busca else ""
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
        publicado = ar.get(end) or next(
            (v for k, v in ar.items() if nome_do_jogador.mac(k) == end), None) or {}
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
            "nome": nome_do_jogador.nome_dado(nome_dado_ao_adaptador(maquina, end)),
            "entrada": entrada or (DENTRO_DA_MAQUINA if bz is not None else ""),
            "sabido": bz is not None and maquina is not None,
            "face": face or "",
            "hub": bool(getattr(mz, "atras_de_hub", False)),
            "varrendo": bool(getattr(bz, "varrendo", False)) and end != busca_em,
            "junto": junto, "usb3": False,
            "modelo": _modelo_do_radio(mz),
            "conectando": bool(busca_em) and end == busca_em,
            "chegou": [str(m.get("aparelho") or "") for m in movimentos
                       if m.get("estado") == "chegou"
                       and nome_do_jogador.mac(m.get("destino")) == end],
        })
        if caminho:
            portas.append({"id": f"porta-{end}", "caminho": caminho, "usb": "2.0",
                           "ocupa": end, "grupo": _grupo_da_porta(caminho),
                           "rotulo": entrada or caminho})
    sino = _quedas_por_adaptador(em_fundo.em_fundo("sino", _ler_o_historico, 60.0),
                                 caminho_para_endereco, maquina, controladores)
    lido_do_sino = em_fundo.lido("sino") or {}
    desde = str(lido_do_sino.get("desde") or "")
    for lug in lugares:
        lug["quedas"] = sino.get(lug["id"], [])
        if lug["quedas"] and desde:
            lug["quedas_desde"] = desde[8:10] + "/" + desde[5:7]

    endereco_do_caminho = {str(getattr(a, "caminho", "")): nome_do_jogador.mac(a.endereco)
                           for a in adaptadores_bz}
    aparelhos = _aparelhos_da_cena(ctx, st, governador, esperando, aparelhos_bz,
                                   endereco_do_caminho, enderecos)
    _com_a_categoria_do_enlace(aparelhos, enlaces)
    no_ar = (frozenset(_so_hex(a.endereco) for a in aparelhos_bz if a.conectado is True)
             | frozenset(_so_hex(str(c.get("uniq") or "")) for c in ctx.conectados))
    pareados = frozenset(
        (endereco_do_caminho.get(str(a.adaptador), ""), nome_do_jogador.mac(a.endereco))
        for a in aparelhos_bz if a.pareado)
    falhas = _os_que_nao_conectaram(ctx, movimentos, agora, enderecos, no_ar, pareados)
    falhas += _os_que_nao_viraram_controle(
        em_fundo.em_fundo("zumbis", _ler_os_zumbis, 2.0), enderecos, falhas, time.monotonic())
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
                      "vagas": [nome_do_jogador.mac(v) for v in p.get("vagas") or ()],
                      "lugar": nome_do_jogador.mac(end)}
            break
        if pedido:
            break
    if pedido:
        quem = str(pedido["uniq"])
        dono = next((a for a in aparelhos if _so_hex(str(a["id"])) == _so_hex(quem)), None)
        pedido["uniq"] = str(dono["id"]) if dono else quem
    pedindo = _quem_pede_para_parear(central, lugares, aparelhos_bz)
    proposta = _a_proposta_da_cena(central.get("proposta"), aparelhos)
    lugares = _na_ordem_dela(lugares)
    # O acionador declarado no `maquina.json` mora no primeiro adaptador, como no desenho r3-08-14.
    aparelhos += _os_acionadores_declarados(declaracao_viva, lugares)
    buscas: dict[str, object] = {
        nome_do_jogador.mac(m.get("destino")): (
            str(m.get("aparelho") or ""), float(m.get("quando") or 0.0))
        for m in esperando if nome_do_jogador.mac(m.get("destino"))}
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
        "quem_recebe": _quem_recebe_da_mesa(ctx, declaracao_viva),
        "colorway_de": _colorways_da_mesa(ctx),
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
    # as caixas nascem fechadas (desenho aprovado de 05/10/2026): abre a que o usuário clicar, ou a
    # que pede atenção (o controle esperando, o que não conectou)
    return next((str(lug["id"]) for lug in lugares if lug.get("nao_conectou")), None)


def _chave_da_ordem(endereco: object) -> str:
    """A chave do adaptador na ordem gravada: o ENDEREÇO, a chave dele em"""
    perfil._com_o_src()
    from hefesto_dualsense4unix.utils.maquina import chave_do_adaptador

    return chave_do_adaptador(endereco) or ""


def _na_ordem_dela(lugares: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Os adaptadores na ORDEM QUE ELA ARRASTOU, gravada no adaptador pelo endereço.

    Decisão de 25/09/2026 (``utils/maquina.AdaptadorDeclarado.ordem``).
    Quem ela nunca arrastou vem depois, na ordem de sempre.  <!-- noqa-acento: citação literal -->

    A ordem anterior a 28/09/2026 morava no ``gui_prefs``, pela chave do lugar, e vale (traduzida
    pelos adaptadores da tela) até ela arrastar de novo (:func:`_a_ordem_de_antes`).
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
    return agora - _prazo_desde(m) <= ESPERA_NA_TELA_S


def _prazo_desde(m: dict[str, Any]) -> float:
    """O começo do prazo, o mesmo da central: o ``Pair`` que deu, senão o começo do movimento."""
    return float(m.get("prazo_desde") or m.get("quando") or 0.0)


_NAO_CHEGOU_NA_CENTRAL = "nao_chegou"  # (noqa-acento): chave de máquina da central
_RECUSA_DA_CENTRAL = "ocupado"
_DISPENSADOS: set[str] = set()


def _os_que_nao_conectaram(ctx: Contexto, movimentos: list[dict[str, Any]], agora: float,
                           enderecos: list[str],
                           no_ar: frozenset[str] = frozenset(),
                           pareados: frozenset[tuple[str, str]] = frozenset(),
                           ) -> list[dict[str, Any]]:
    """A linha «Não Conectou» de cada APARELHO que não chegou e não está no ar.

    Não chegou é a central dizendo «não chegou» (qualquer motivo, menos a recusa do um-por-vez, que
    não começou nada, e a busca que ela desligou), ou o «esperando» que passou de
    :data:`ESPERA_NA_TELA_S`.

    A linha tem aparelho (ESQUECER-E-LIMPAR-AS-CONEXOES-01, D-3009-A-LINHA-TEM-APARELHO,
    30/09/2026): a busca que ninguém respondeu (movimento sem endereço) virava «DualSense · Não
    Conectou», com o desenho do controle, a borda laranja e a caixa que abria:
    o *«controle fantasma»* dela.  <!-- noqa-acento: citação literal -->

    Agora a linha só existe enquanto há aparelho de verdade que não chegou e não está no ar em
    adaptador nenhum, por transporte nenhum (``no_ar``: o ``Connected`` do BlueZ e o ``uniq`` do
    daemon, o cabo também), e some no tique em que ele aparece. Uma por aparelho, como a central
    guarda: o «Conectar» seguinte no mesmo adaptador não apaga a linha de quem ficou sem casa. O fim
    da busca sem ninguém é dito no «Procurar».

    A meia chave é da central e a tela só mostra (achado 8 da auditoria de 26/09,
    A-CAIXA-FICA-ONDE-ELA-ABRIU-01): quem tira a chave do ``Pair`` que não conectou é a central,
    antes do «não chegou» (``central_do_radio._esquecer_a_meia_chave``), e quem tira a linha é o X
    dela (``radio.dispensar``).
    """
    da_mesa = {_so_hex(str(e.get("uniq") or "")): e for e in ctx.mesa}
    linhas: list[dict[str, Any]] = []
    for m in movimentos:
        aparelho = nome_do_jogador.mac(m.get("aparelho")) if m.get("aparelho") else ""
        destino = nome_do_jogador.mac(m.get("destino"))
        if not aparelho or destino not in enderecos or _so_hex(aparelho) in no_ar:
            continue
        idade = agora - float(m.get("quando") or 0.0)
        estado = str(m.get("estado") or "")
        motivo = str(m.get("motivo") or "")
        falhou = ((estado == _NAO_CHEGOU_NA_CENTRAL
                   and motivo not in (_RECUSA_DA_CENTRAL, _central_do_radio.MOTIVO_DESLIGADA))
                  or (estado == "esperando" and agora - _prazo_desde(m) > ESPERA_NA_TELA_S))
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
        return [(nome_do_jogador.mac(link.get("adaptador")),
                 _so_hex(str(link.get("controle") or "")))
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


def _os_desligados(aparelhos_bz: tuple[Any, ...], endereco_do_caminho: dict[str, str],
                   ja: list[dict[str, Any]],
                   no_usb: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """Os aparelhos com pareamento NESTE adaptador e fora do ar — o item 3: o"""
    no_ar = {_so_hex(a.endereco) for a in aparelhos_bz if a.conectado is True}
    vivos = {_so_hex(str(a["id"])) for a in ja if not a.get("nao_conectou")}
    falhas = {(_so_hex(str(a.get("aparelho") or "")), a["lugar"])
              for a in ja if a.get("nao_conectou")}
    nomes = nome_do_jogador.nomes_por_endereco(aparelhos_bz)
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
        alias = "" if nome_do_jogador.ALIAS_QUE_E_ENDERECO.fullmatch(alias) else alias
        if em_fundo.e_controle_do_bluez(a):
            tipo, nome = "controle", nomes.get(nome_do_jogador.mac(a.endereco), "")
            rotulo = (alias if alias and not nome_do_jogador.e_nome_de_fabrica(alias)
                      else "DualSense")
        else:
            tipo = _tipo_que_ela_disse(a.endereco) or _tipo_do_aparelho(
                str(getattr(a, "icone", "") or ""), a.classe, getattr(a, "aparencia", None))
            nome, rotulo = alias, alias or PALAVRA_DO_TIPO.get(tipo, "aparelho").capitalize()
        fora.append({
            "id": nome_do_jogador.mac(a.endereco), "aparelho": nome_do_jogador.mac(a.endereco),
            "tipo": tipo,
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


def _a_luz_acesa(c: dict[str, Any], st: dict[str, Any]) -> bool:
    """A barra de luz do controle, para a marca da linha: apagada só quando o motor diz apagada.

    Quem decide é o dono das outras abas (`cartao_do_controle.rotulo_lightbar`, traduzido por
    `a04_iluminacao.estado_da_tira`, o mesmo que a Perfis pergunta): a fonte nossa com a barra
    desligada OU de cor preta é «apagada». Sem fonte, sem cor ou com a Steam segurando o controle,
    a marca fica acesa, porque a tela nunca diz «desligada» do que ninguém mediu.
    """
    from hefesto_dualsense4unix.interface.cartao_do_controle import rotulo_lightbar

    from . import a04_iluminacao

    estado = a04_iluminacao.estado_da_tira(rotulo_lightbar(c, st)[0])
    return estado != a04_iluminacao.APAGADA


def _a_taxa_da_ponte(da_ponte: dict[tuple[str, str], dict[str, Any]], uniq: str,
                     ponte: object) -> dict[str, Any]:
    """`hz_ponte` e `ponte_cedendo` da ponte que o controle tem de pé (som ou vibração)."""
    tipo = {"som": "som", "haptica": "vibracao"}.get(str(ponte), "")
    publicada = da_ponte.get((_so_hex(uniq), tipo)) if tipo else None
    if publicada is None:
        return {"hz_ponte": None, "ponte_cedendo": False}
    hz = publicada.get("hz")
    return {"hz_ponte": hz if isinstance(hz, (int, float)) else None,
            "ponte_cedendo": bool(publicada.get("cedendo"))}


def _a_proposta_da_cena(
    publicada: object, aparelhos: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """`radio_central.proposta` na forma da cena: o controle pelo id da tela e o destino; pelo
    sinal, também a marca e os dois dBm (o Equilibrar diz «sinal fraco»)."""
    if not isinstance(publicada, dict) or not publicada:
        return None
    dono = next((a for a in aparelhos
                 if _so_hex(a["id"]) == _so_hex(str(publicada.get("controle") or ""))), None)
    if dono is None:
        return None
    pelo_sinal = ({"pelo_sinal": True, "sinal_aqui": publicada.get("sinal_aqui"),
                   "sinal_la": publicada.get("sinal_la")} if publicada.get("pelo_sinal") else {})
    return {"controle": dono["id"], "destino": nome_do_jogador.mac(publicada.get("destino")),
            **pelo_sinal}


def _aparelhos_da_cena(ctx: Contexto, st: dict[str, Any], governador: dict[str, Any],
                       esperando: list[dict[str, Any]], aparelhos_bz: tuple[Any, ...],
                       endereco_do_caminho: dict[str, str],
                       enderecos: list[str]) -> list[dict[str, Any]]:
    """Os controles pelo `state_full` (as quatro chaves por controle) e o resto pelo BlueZ."""
    da_mesa = {str(m.get("uniq") or ""): m for m in ctx.mesa}
    alem = {_so_hex(str(p.get("uniq") or "")): (p.get("tipo"), bool(p.get("alem_do_limite")))
            for publicado in governador.values()
            for p in _dicionario(publicado).get("pontes") or ()}
    pausada = {_so_hex(str(p.get("uniq") or "")): bool(p.get("pausada_pelo_sinal"))
               for publicado in governador.values()
               for p in _dicionario(publicado).get("pontes") or ()}
    da_ponte = {(_so_hex(str(p.get("uniq") or "")), str(p.get("tipo") or "")): p
                for publicado in governador.values()
                for p in _dicionario(publicado).get("pontes") or ()}
    ordem_da_vaga = {_so_hex(str(p.get("uniq") or "")): i
                     for publicado in governador.values()
                     for i, p in enumerate(_dicionario(publicado).get("pontes") or ())}
    alias = nome_do_jogador.nomes_por_endereco(aparelhos_bz)
    fora: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for c in st.get("controllers") or ():
        if not isinstance(c, dict) or str(c.get("transport") or "").lower() != "bt":
            continue
        uniq = str(c.get("uniq") or "")
        adaptador = nome_do_jogador.mac(c.get("adaptador"))
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
        nome_bz = alias.get(nome_do_jogador.mac(uniq), "")
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
            "hz_mov": c.get("hz_movimento"), "hz_voz": c.get("hz_voz"), "luz": _a_luz_acesa(c, st),
            "sinal": c.get("sinal_dbm"),
            "ponte_pausada": pausada.get(_so_hex(uniq), False),
            **_a_taxa_da_ponte(da_ponte, uniq, ponte),
            "esperando": False, "fixo": False,
        })
        vistos.add(_so_hex(uniq))
    for m in esperando:
        quem = _so_hex(str(m.get("aparelho") or ""))
        if not quem:
            continue
        ja = next((a for a in fora if _so_hex(a["id"]) == quem), None)
        if ja is not None:
            ja.update(lugar=nome_do_jogador.mac(m.get("destino")), esperando=True)
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
                     "lugar": nome_do_jogador.mac(m.get("destino")),
                     "nome": str(m.get("nome") or ""),
                     "modalias": str(m.get("modalias") or ""),
                     "jogador": eu.get("jogador"),
                     "rotulo": f"Player {eu['jogador']}" if eu.get("jogador") else "",
                     "cor": cor if cor.startswith("#") else "",
                     "cor_nome": "" if str(eu.get("nome") or "") in ("", _cor_desconhecida())
                     else str(eu["nome"]),
                     "esperando": True, "fixo": False})
        vistos.add(quem)
    for a in aparelhos_bz:
        endereco = nome_do_jogador.mac(a.endereco)
        adaptador = endereco_do_caminho.get(str(a.adaptador), "")
        # Um DualSense que o daemon não publica não vira «outro aparelho».
        if (not a.conectado or not adaptador or _so_hex(endereco) in vistos
                or "V054C" in str(getattr(a, "modalias", "")).upper()):
            continue
        dela = _tipo_que_ela_disse(endereco)
        fora.append({"id": endereco,
                     "tipo": dela or _tipo_do_aparelho(getattr(a, "icone", ""), a.classe,
                                                       getattr(a, "aparencia", None)),
                     "tipo_dela": bool(dela),
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

    Uma linha por adaptador que viu o aparelho, com o sinal medido POR ELE
    (D-3009-A-LISTA-E-DO-ADAPTADOR-ACESO, 30/09/2026, a validar pelo usuário). A lista antiga era
    por endereço só: o mesmo aparelho visto por dois ficava com o sinal do último que o BlueZ listou
    e o «Parear» mandava o chip aceso como destino de um aparelho que ele talvez nunca tivesse
    visto. O painel desenha só as do adaptador do chip aceso (:func:`_moldes_de_painel`).

    ``buscas`` é ``{adaptador: quem busca ali}`` (a identidade da busca do Hefesto em cada
    adaptador); quando muda, a ordem daquele adaptador recomeça (:func:`_na_ordem_da_chegada`).

    Quem é controle e o nome da linha (O-PAREAR-ESPERA-O-CLIQUE-01): o tipo pergunta à classe, ao
    ``Icon`` e só então ao ``Modalias`` (:func:`em_fundo.e_controle_do_bluez`, o dono da central);
    antes de parear o BlueZ não tem o ``Modalias`` do DualSense e a linha caía no desenho genérico.
    O nome é o que o usuário deu ou o aparelho anuncia (:func:`nome_do_jogador.nomes_por_endereco`);
    sem ele, «DualSense» ou a palavra do tipo, nunca o endereço.
    """
    ligados = {_so_hex(a["id"]) for a in ja}
    adaptador_de = {str(getattr(a, "caminho", "")): nome_do_jogador.mac(a.endereco)
                    for a in adaptadores_bz}
    nomes = nome_do_jogador.nomes_por_endereco(aparelhos_bz)
    vistos: dict[tuple[str, str], dict[str, Any]] = {}
    for a in aparelhos_bz:
        onde = adaptador_de.get(str(a.adaptador), "")
        if not onde or a.conectado or a.rssi is None or _so_hex(a.endereco) in ligados:
            continue
        tipo = ("controle" if em_fundo.e_controle_do_bluez(a)
                else _tipo_do_aparelho(getattr(a, "icone", ""), a.classe,
                                       getattr(a, "aparencia", None)))
        vistos[(onde, nome_do_jogador.mac(a.endereco))] = {
            "id": nome_do_jogador.mac(a.endereco), "adaptador": onde,
            "nome": nomes.get(nome_do_jogador.mac(a.endereco)) or (
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
            return nome_do_jogador.mac(ordem[0].endereco)
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
    """As três telas do «Mapear entrada a entrada», pelo laço (ENTRADA-A-ENTRADA-02)."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
    from hefesto_dualsense4unix.interface import calibracao_das_entradas as calib

    # `/sys`, e com ela encaixando o DualSense o kernel o segura por segundos.
    foto = _laco().foto_sem_esperar()
    contador, quem = "", ""
    if foto.get("estado") == ee.SENTADA:
        contador = (f'Entrada {foto.get("passo")} de {foto.get("total")} '
                    f'<span class="pt">·</span> {calib.SEM_SAIR_DA_CADEIRA}')
        pergunta = foto.get("pergunta") or {}
        quem = (f'{_x(pergunta.get("especie") or "")} <span class="pt">·</span> '
                f'<code>{_x(pergunta.get("caminho") or "")}</code>') if pergunta else ""
    elif foto.get("estado") == ee.EM_PE:
        contador = f'Entrada {foto.get("passo")} de {foto.get("total")}'
        quem = calib.PROCURANDO
    # No fim, o convite mora no «?» da tela: o corpo fica sem frase explicativa.
    nada = _monta().NADA_A_DIZER
    return {"entrada-tela": foto.get("tela") or "", "entrada-contador": contador or nada,
            "entrada-quem": quem or nada}


def campos_do_radio(ctx: Contexto) -> dict[str, Any]:
    """Os campos da seção rádio e adaptadores, pela cena da máquina do usuário."""
    global _CENA_NA_TELA
    cena = cena_do_radio(ctx)
    _CENA_NA_TELA = cena
    campos = campos_da_secao(cena, segurar=True)
    with contextlib.suppress(Exception):
        campos.update(_campos_da_cerimonia())
    # A janela do acionador mora fora da `#rd-secao`, mas pinta da mesma cena.
    campos.update(campos_do_acionador(cena))
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

    Decisão de 25/09/2026:
    *«segurar a área do conector e arrastar ela pra mudar de ordem entre eles»*.
    <!-- noqa-acento: citação literal -->

    O roteiro da página solta a caixa no lugar e manda a ordem NOVA, de cima para baixo, pelos
    ``data-id`` (o endereço de cada adaptador), que vai para o adaptador pelo dono do nome dele
    (``utils/maquina.guardar_ordem_dos_adaptadores``, desde 28/09/2026; antes ia para o
    ``gui_prefs``, pelo lugar, e a lista de lá sai aqui). Id que não está na tela recusa: a ordem
    nunca inventa adaptador.
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
    em_fundo.esquecer("maquina")
    _CENA_NA_TELA["lugares"] = [na_tela[i] for i in ids] + [
        lug for i, lug in na_tela.items() if i not in ids]


def _gravar_o_nome(endereco: str, nome: str) -> Any:
    """O nome é do ADAPTADOR, pelo endereço, e mora no `maquina.json`; o `Alias`"""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.entrada_a_entrada import dar_nome_ao_adaptador

    feito = dar_nome_ao_adaptador(endereco, nome)
    em_fundo.esquecer("maquina")
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
    novo = nome_do_jogador.nome_dado(str(o.get("valor") or ""))
    if novo == str(lug.get("nome") or ""):
        return None
    feito = _gravar_o_nome(str(lug["id"]), novo)
    if not getattr(feito, "gravou", False):
        raise RuntimeError("o nome não foi gravado")
    return None


def _alias_do_aparelho(endereco: str, nome: str) -> Any:
    """O `Alias` de um APARELHO no BlueZ, pelo dono (`bluez_dbus`), em TODOS os objetos dele.

    O nome é do aparelho e o BlueZ o guarda por adaptador. A função escrevia no PRIMEIRO objeto da
    árvore: com o controle pareado em dois adaptadores o nome ia para o de onde ele não estava e a
    tela lia o outro (lista dela de 25/09, passo a2: *«O nome renomeado não aparece»*). Agora vai
    para todos e vale onde ele reconectar. Nome vazio devolve o de fábrica (o BlueZ faz isso com o
    ``Alias`` em branco) e a tela volta
    ao «Player N».  <!-- noqa-acento: citação literal -->
    Devolve a primeira escrita que deu, ou a primeira recusa quando nenhuma deu.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import bluez_dbus

    dono = bluez_dbus.dono()
    caminhos = dono.caminhos_do_aparelho(endereco)
    if not caminhos:
        raise RuntimeError("o Bluetooth do sistema não achou este aparelho agora")
    escritas = [dono.escrever_propriedade(
        caminho, bluez_dbus.APARELHO, "Alias", "s", nome, quem="tela") for caminho in caminhos]
    em_fundo.esquecer("bluez")
    return next((e for e in escritas if getattr(e, "feita", False)), escritas[0])


@gesto("08-conexoes.html", "aparelho-renomear", grava="escrever_propriedade")
def aparelho_renomear(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O nome de um aparelho — Vitória, Caixa de som — no `Alias` do BlueZ."""
    if _so_o_foco(o):
        return {"armou": True}
    ap = _aparelho_na_tela(str(o.get("alvo") or ""))
    novo = str(o.get("valor") or "").strip()
    if ap.get("tipo") == TIPO_ENTRADA:
        # O acionador não é do Bluetooth: o nome mora na declaração dele (a chave do kernel).
        if novo != str(ap.get("nome") or ""):
            _declarar_o_acionador(p, {"acionadores": {str(ap["chave"]): {"nome": novo or None}}})
        return None
    if ap.get("tipo") == "controle":
        novo = nome_do_jogador.nome_dado(novo)
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
    em_fundo.esquecer("bluez")
    with contextlib.suppress(Exception):
        _tirar_a_linha(p, linha)
    _ligar_a_busca(p, True, lid)
    # O mesmo clique é a escolha do usuário: a central pareia ESTE endereço quando a janela o
    # ver. Se não aceitar agora, a busca segue aberta e o «Parear» da lista fecha.
    with contextlib.suppress(Exception):
        _pedir_ao_radio(p, str(linha["aparelho"]), lid)
    _abrir_na_tela(lid)
    return {"armou": True}


@gesto("08-conexoes.html", "parear-o-pedido", grava="radio.mover")
def parear_o_pedido(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """O «Parear» do cartão do controle que pede para parear: o mesmo ``radio.mover`` do
    «Mover», no adaptador que o ouve — a central tira o par velho do destino, espera o
    controle (ele já está em modo de parear), pareia, confere e esquece a origem."""
    alvo, destino = nome_do_jogador.mac(o.get("alvo")), nome_do_jogador.mac(o.get("destino"))
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
    em_fundo.esquecer("bluez")


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
    if ligada:
        feita = isinstance(busca, dict) and (
            not destino
            or nome_do_jogador.mac(busca.get("adaptador")) == nome_do_jogador.mac(destino))
    else:
        feita = busca is None
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
    em_fundo.esquecer("maquina")
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
    em_fundo.esquecer("maquina")


@gesto("08-conexoes.html", "entrada-parar")
def entrada_parar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """«Já chega por hoje»: fecha, e nada se perde — cada resposta já foi."""
    _laco().parar()
    return {"armou": True}


PONTE = {"chamar", "machine_declare", "resultado", "mic_canal_set_detalhado"}
METODOS = {"controller.target.set", "radio.mover", "radio.ponte.ligar_aqui",
           "radio.busca.set", "radio.dispensar"}


PAGINA = "08-conexoes.html"
PISO_DA_ABA = 52
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
    {"pagina": PAGINA, "gesto": "externo-modo",  # (noqa-acento) id
     "clique": {"externo": "aa:bb:cc:00:00:01", "valor": "switch"},
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"modo": "switch"}}}], {})]},
    {"pagina": PAGINA, "gesto": "externo-botoes",  # (noqa-acento) id
     "clique": {"externo": "aa:bb:cc:00:00:01", "valor": "nintendo"},
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"botoes": "nintendo"}}}], {})]},
    {"pagina": PAGINA, "gesto": "externo-cor",  # (noqa-acento) id
     "clique": {"externo": "aa:bb:cc:00:00:01", "valor": "Cosmic Red"},
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"cor": "Cosmic Red"}}}], {})]},
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
    "externo-modo": _NO_MAQUINA,
    "externo-botoes": _NO_MAQUINA,
    "externo-cor": _NO_MAQUINA,
    "receptor-descobrir": "guarda o passo na tela; a banda achada vai ao `maquina.json` no tique "
                          "que fecha a medida, e o `state_full` não a republica",
    "ignorar": "a dispensa de uma ordem vai ao `maquina.json`; o `state_full` não a publica",
    "examinar-portas": "não toca o daemon: muda a tira do Check-up no tique seguinte",
    "escolher-aparelho": "primeiro tempo do gesto de dois: guarda o aparelho na mão e "
                         "não chama a ponte",
    "escolher-entrada": _O_MAPA,
    "tirar-daqui": _O_MAPA,
    "nova-entrada": _O_MAPA,
    "nova-extensao": _O_MAPA,
    "nova-face": _O_MAPA,
    "novo-hub": "só abre a pergunta do hub: é estado de tela e não chama a ponte",
    "novo-hub-cancelar": "só fecha a pergunta do hub: é estado de tela e não chama a ponte",
    "novo-hub-gravar": _O_MAPA,
    "adaptador-renomear": _NO_MAQUINA,
    "aparelho-renomear": _NO_BLUEZ,
    "entrada-face": _NO_MAQUINA,
    "entrada-nao-alcanco": _NO_MAQUINA,
    "adaptador-reordenar": "grava a ordem das caixas no `gui_preferences.json`, "
                           "que o daemon não lê",
    "dono-renomear": _NO_BLUEZ,
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


def selo_do_estado(rotulo: str, valor: str = "", estado: str = "ok", dica: str = "") -> str:
    """Um selo da linha: «Mic ✓», «Bateria 64% · carregando», «Visto como Xbox 360».

    `dica` é o `title` do selo inteiro, para o que a linha não cabe dizer (a Mira diz os números).
    O valor ganha a primeira letra maiúscula aqui, o dono único («Mudo», «Sem ponte»): ele fica
    sozinho à direita da linha, e a tela abre todo texto com maiúscula (19/10/2026).
    """
    miolo = html.escape(rotulo)
    if valor:
        miolo += f" <b>{html.escape(valor[:1].upper() + valor[1:])}</b>"
    if estado == "ok":
        miolo += f' <i class="certo">{CERTO}</i>'
    classe = f"est {estado}" if estado else "est"
    titulo = f' title="{html.escape(dica, quote=True)}"' if dica else ""
    return f'<span class="{classe}"{titulo}>{miolo}</span>'


def modo_da_fileira(st: dict[str, Any]) -> str:
    """O «Modo de conexão» da linha: o nome do chip aceso na aba Jogar.

    O pedido diz *«Modo de conexão (DualSense)»*, o modo escolhido na fileira da Jogar, não a
    posição do interruptor. O dono do chip aceso é `a01_jogar._estado_da_tela` e o nome vem de
    `painel.CHIPS_DA_ESCADA`. Com o Hefesto desligado a palavra é a do interruptor (``Nativo``); sem
    leitura, ``Pelo Hefesto``, verdade enquanto o daemon responde.
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
    """Os selos de UM controle, lidos do daemon vivo e da declaração.

    `c` é a entrada do `state_full` (o `ctx.conectados`), `eu` a da mesa (número e máscara por
    aparelho), `st` o estado inteiro. Vale para todo transporte e todo modo: nenhum ramo pergunta
    qual é o controle nem quantos há.
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
    # Rádio e adaptadores. (noqa-acento: citação literal)
    return {"est-mic": mic, "est-som": som, "est-modo": modo_da_linha, "est-visto": visto}


def nome_com_a_bateria(rotulo: str, pct: object) -> str:
    """«Cosmic Red • BT • 85%» — o rótulo curto e a carga, quando ela é lida."""
    bateria = _texto_da_bateria(pct)
    if not rotulo or not bateria or bateria == TRAVESSAO_DA_LINHA:
        return rotulo
    return f"{rotulo}{_PONTO}{html.escape(bateria)}"


TRAVESSAO_DA_LINHA = "—"


# `dono_na_linha` (importada no topo) é a regra «o nome, ou o Pn», que mora em `monta` desde
# 07/10/2026: a 02 e a Calibrar dizem quem joga pela mesma regra, e o nome daqui é o alias.

_SO_O_NUMERO = re.compile(r"\s*p\s*\d+\s*", re.IGNORECASE)


@gesto("08-conexoes.html", "dono-renomear", grava="escrever_propriedade")
def dono_renomear(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O nome do jogador dono do controle — pelo dono do nome (o `Alias`)."""
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("dono-renomear: o clique não disse em qual controle")
    novo = nome_do_jogador.nome_dado(str(o.get("valor") or ""))
    if _SO_O_NUMERO.fullmatch(novo):
        novo = ""
    if novo == nome_do_jogador.nomes_dos_donos().get(nome_do_jogador.mac(uniq), ""):
        return
    endereco = _so_hex(uniq)
    if len(endereco) != 12:
        raise RuntimeError(_sem_endereco())
    endereco = ":".join(endereco[i:i + 2] for i in range(0, 12, 2)).upper()
    escrita = _alias_do_aparelho(endereco, novo)
    if not getattr(escrita, "feita", False):
        raise RuntimeError("o Bluetooth do sistema não gravou o nome novo")


# é o estado, e o tique a pinta. <!-- noqa-acento: citação literal -->
MAPEAR_DIZ = {
    "parado": "Conecte o DualSense por USB numa entrada do computador.",
    "esperando": "Conecte o DualSense por USB numa entrada do computador.",
    "porta": "Conecte um DualSense em cada entrada USB do seu dispositivo.",
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
