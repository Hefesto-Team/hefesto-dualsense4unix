"""dicas_da_conexao.py — as dicas da aba Conexões: cartões de poucas palavras, com UM gesto.

AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01 (04/10/2026), o desenho 4 que ela aprovou. Ela pediu «a ideia é
educar o user: pouco texto, muito mais intuitivo e orgânico». O quadro de frases (CERTO/AJUSTAR) e o
quadro «Sugestão de Conexão» viram uma fileira de cartões:

* **três a cinco palavras** no título («Meio sufocado», «Wi-Fi colado nos rádios»);
* **o pictograma do que muda** (`P2 · Meio → Direita`) quando há destino;
* **um botão de ação** por cartão, e só um;
* **o porquê numa frase só**, atrás do ⓘ;
* os **quatro que mais pesam** aparecem, numa fileira de cartões da mesma altura; o próximo entra
  quando ela ignora ou resolve um (sem «mais N», desenho aprovado de 05/10/2026). O que está certo
  não ganha linha: sem dica nenhuma, a aba diz só «Tudo certo».

Este módulo é puro: entram fatos já lidos (as ordens do exame, a proposta da central, as quedas do
Wi-Fi), sai o :class:`Painel`. Quem desenha é ``interface.conexoes.html_das_dicas``; quem lê os
fatos é o pacote da aba 08. Nenhuma frase de medição nasce aqui: o porquê vem da ordem ou da
conferência que o dono já escreveu, cortado na primeira frase.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens

PALAVRAS_NO_TITULO = 5
CARTOES_VISIVEIS = 4
#: o gesto do cartão, em até duas palavras (desenho aprovado de 05/10/2026).
PALAVRAS_NO_GESTO = 2
#: a frase do ⓘ, em caracteres — o resto é o que a ordem já diz na tela de detalhe.
LIMITE_DA_FRASE = 160

GRAVE = "grave"
AJUSTE = "ajuste"
NOTA = "nota"
PESO_DO_NIVEL = {GRAVE: 3, AJUSTE: 2, NOTA: 1}
#: a palavra de cada nível, para quem não vê a cor (o cartão nunca fala só em cor).
PALAVRA_DO_NIVEL = {GRAVE: "Urgente", AJUSTE: "Ajuste", NOTA: "Nota"}

#: o desenho de cada tipo de dica (símbolos do sprite da aba 08).
ICONE_RADIO = "radio"
ICONE_WIFI = "wifi"
ICONE_TECLADO = "teclado"
ICONE_ENTRADA = "hub"
ICONE_AJUDA = "ajuda"

# O que o botão faz.
MOVER = "mover"
MAPA = "mapa"
IGNORAR = "ignorar"
VOLTAR_A_MOSTRAR = "voltar-a-mostrar"

PAGINA_DO_MAPA = "mapa-das-portas.html"
GESTO_DE_MOVER = "aceitar-sugestao"
GESTO_DE_IGNORAR = "ignorar"

ROTULO_VER_NO_MAPA = "Ver no mapa"
ROTULO_IGNORAR = "Ignorar"
ROTULO_VOLTAR_A_MOSTRAR = "Mostrar"
ROTULO_PAREAR = "Parear"

NADA_A_MUDAR = "Tudo certo"
SEM_CAUSA_DA_QUEDA = "A placa saiu do barramento e voltou; o diário do kernel não diz a causa."

#: título, ícone e rótulo do botão de cada ordem do catálogo (``ordens_da_mesa``).
DA_ORDEM: dict[str, tuple[str, str, str]] = {
    ordens.R1_RADIO_LARGO_NO_MESMO_HUB: (
        ICONE_WIFI, "Wi-Fi colado nos rádios", ROTULO_VER_NO_MAPA),
    ordens.R2_DOIS_RADIOS_COLADOS: (
        ICONE_RADIO, "Dois rádios colados", ROTULO_VER_NO_MAPA),
    ordens.R3_DONGLE_ATRAS_DE_HUB: (
        ICONE_RADIO, "Bluetooth atrás de hub", ROTULO_VER_NO_MAPA),
    ordens.R4_TECLADO_SO_NO_HUB: (
        ICONE_TECLADO, "Teclado só no hub", ROTULO_VER_NO_MAPA),
    ordens.R5_DONGLE_DORME: (
        ICONE_RADIO, "Bluetooth pode dormir", ROTULO_VER_NO_MAPA),
    ordens.R6_ENTRADA_RECLAMOU_DE_CORRENTE: (
        ICONE_ENTRADA, "Entrada com pouca energia", ROTULO_VER_NO_MAPA),
}

#: título, ícone e a palavra do «certo» de cada conferência do exame (``exame_da_mesa``).
DA_CONFERENCIA: dict[str, tuple[str, str, str]] = {
    "energia_do_radio": (ICONE_RADIO, "Rádio pode desligar", "Energia do rádio"),
    "energia_das_portas": (ICONE_ENTRADA, "Entrada com pouca energia", "Energia das entradas"),
    "suporte_ao_controle": (ICONE_AJUDA, "Suporte ao controle ausente", "Suporte ao controle"),
    "pareamentos": (ICONE_RADIO, "Pareamento incompleto", "Pareamentos salvos"),
    "vizinhanca_das_portas": (
        ICONE_WIFI, "Wi-Fi colado no Bluetooth", "Rádios longe um do outro"),
}
#: a conferência sem verbete (a leitura que falhou, o exame que não correu).
TITULO_SEM_VERBETE = "Não deu para olhar"

_FIM_DA_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ«\"])")
_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Acao:
    """O único botão do cartão. ``href`` é navegação; ``gesto`` é o que o piloto leva ao Python."""

    tipo: str
    rotulo: str
    gesto: str = ""
    href: str = ""
    dados: tuple[tuple[str, str], ...] = ()
    #: o `title` do botão (o que ele faz, em uma frase do dono).
    titulo: str = ""


@dataclass(frozen=True)
class Dica:
    """Um cartão. ``titulo`` tem de três a cinco palavras; ``porque`` é UMA frase."""

    chave: str
    icone: str
    titulo: str
    nivel: str
    acao: Acao
    porque: str = ""
    #: «O que fazer: …», só para o cartão cujo botão não diz o que fazer (a conferência sem mapa).
    cura: str = ""
    de: str = ""
    para: str = ""
    detalhe: str = ""
    ignorar: Acao | None = None
    calada: bool = False

    @property
    def peso(self) -> int:
        return PESO_DO_NIVEL[self.nivel]


@dataclass(frozen=True)
class Painel:
    """O que a aba mostra: os cartões que pesam, o resto em «mais N», e o que está certo."""

    visiveis: tuple[Dica, ...] = ()
    demais: tuple[Dica, ...] = ()
    certos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def vazio(self) -> bool:
        return not self.visiveis and not self.demais


def limitar_o_titulo(titulo: str) -> str:
    """Corta no limite de palavras, sem reticências (passar do limite é erro de quem escreveu)."""
    return " ".join(titulo.split()[:PALAVRAS_NO_TITULO])


def uma_frase(texto: str, limite: int = LIMITE_DA_FRASE) -> str:
    """A primeira frase do texto, sem marcação e no limite — o que cabe atrás do ⓘ."""
    limpo = " ".join(_TAGS.sub(" ", str(texto or "")).split())
    primeira = _FIM_DA_FRASE.split(limpo, maxsplit=1)[0].strip()
    if len(primeira) <= limite:
        return primeira
    corte = primeira[:limite].rsplit(" ", 1)[0].rstrip(",;:")
    return corte + "…"


def _nivel_do_estado(estado: str) -> str:
    por_estado = {"problema": GRAVE, "atencao": AJUSTE}  # (noqa-acento): chave
    return por_estado.get(estado, NOTA)


def dica_da_ordem(
    ordem: object,
    estado: str,
    *,
    slot: int,
    calada: bool = False,
    de: str = "",
    para: str = "",
    cura: str = "",
    dica_de_ignorar: str = "",
    dica_de_voltar: str = "",
) -> Dica:
    """O cartão de uma ordem do catálogo, com o destino quando ela o tem.

    ``slot`` é a linha do exame onde a ordem mora: o ``ignorar`` a chama por ele.
    """
    chave = str(getattr(ordem, "chave", ""))
    destino = str(getattr(ordem, "destino", "") or "")
    icone, titulo, rotulo = DA_ORDEM.get(chave, (
        ICONE_AJUDA, str(getattr(ordem, "acao", "") or ""),  # (noqa-acento): campo
        ROTULO_VER_NO_MAPA))
    por_que = getattr(getattr(ordem, "por_que_importa", None), "texto", "")
    return Dica(
        chave=chave, icone=icone, titulo=limitar_o_titulo(titulo),
        nivel=_nivel_do_estado(estado),
        acao=_acao_de_ignorar_de_volta(slot, dica_de_voltar) if calada
        else Acao(MAPA, rotulo, href=PAGINA_DO_MAPA),
        porque=uma_frase(por_que), cura=cura,
        de=de if destino else "", para=para if destino else "",
        ignorar=Acao(IGNORAR, ROTULO_IGNORAR, GESTO_DE_IGNORAR, dados=(("v", str(slot)),),
                     titulo=dica_de_ignorar),
        calada=calada,
    )


def _acao_de_ignorar_de_volta(slot: int, titulo: str = "") -> Acao:
    return Acao(VOLTAR_A_MOSTRAR, ROTULO_VOLTAR_A_MOSTRAR, GESTO_DE_IGNORAR,
                dados=(("v", str(slot)),), titulo=titulo)


def dica_da_conferencia(
    chave: str, rotulo: str, estado: str, porque: str, cura: str = ""
) -> Dica:
    """O cartão de uma conferência do exame que não deu certo."""
    icone, titulo, _certo = DA_CONFERENCIA.get(
        chave, (ICONE_AJUDA, limitar_o_titulo(rotulo) or TITULO_SEM_VERBETE, ""))
    return Dica(
        chave=chave, icone=icone, titulo=limitar_o_titulo(titulo), nivel=_nivel_do_estado(estado),
        acao=Acao(MAPA, ROTULO_VER_NO_MAPA, href=PAGINA_DO_MAPA), porque=uma_frase(porque),
        cura=cura)


def o_que_esta_certo(chave: str, rotulo: str) -> str:
    """A palavra curta de uma conferência que deu certo, para a linha «✓ …» do fim."""
    return DA_CONFERENCIA.get(chave, ("", "", limitar_o_titulo(rotulo)))[2]


@dataclass(frozen=True)
class Movimento:
    """A proposta da central: um controle que funciona melhor noutro adaptador."""

    controle: str
    jogador: int | None
    nome_do_controle: str
    de_id: str
    de_nome: str
    para_id: str
    para_nome: str
    controles_no_de: int
    bons: int | None = None
    sufocado: bool = False


def dica_do_movimento(m: Movimento) -> Dica:
    """«Meio sufocado» (o adaptador sem folga) ou «Esquerda dividido em 4», com o de→para."""
    quem = f"P{m.jogador}" if m.jogador is not None else m.nome_do_controle
    if m.sufocado:
        titulo, nivel = f"{m.de_nome} sufocado", GRAVE
        porque = (f"Ele usa só {m.bons} dos 79 canais: está colado no Wi-Fi e nos receptores."
                  if m.bons is not None else "Ele tem poucos canais livres para os controles.")
    else:
        titulo, nivel = f"{m.de_nome} dividido em {m.controles_no_de}", AJUSTE
        porque = (f"{m.controles_no_de} controles dividem o mesmo adaptador: "
                  "um por adaptador fica mais estável.")
    return Dica(
        chave=f"mover:{m.controle}", icone=ICONE_RADIO, titulo=limitar_o_titulo(titulo),
        nivel=nivel,
        acao=Acao(MOVER, f"Mover {quem}", GESTO_DE_MOVER,
                  dados=(("alvo", m.controle), ("destino", m.para_id))),
        porque=uma_frase(porque), de=f"{quem} · {m.de_nome}", para=m.para_nome)


def dica_do_wifi(em_palavras: str, usb3_no_2_4: bool, causa_conhecida: str, nivel: str) -> Dica:
    """O Wi-Fi que cai: «caiu N vezes em M min» e, quando é o USB 3.0 colado no 2,4, a causa."""
    return Dica(
        chave="wifi-caindo", icone=ICONE_WIFI,
        titulo="Wi-Fi caindo" if nivel == AJUSTE else "Wi-Fi apertado", nivel=nivel,
        acao=Acao(MAPA, ROTULO_VER_NO_MAPA, href=PAGINA_DO_MAPA),
        porque=uma_frase(causa_conhecida if usb3_no_2_4 else SEM_CAUSA_DA_QUEDA),
        detalhe=em_palavras)


#: o título e o porquê do cartão do receptor 2.4G que sofre; a causa é «possível», nunca confirmada.
TITULO_DO_RECEPTOR = {"teclado": "Teclado errando", "mouse": "Mouse engasgando"}
TITULO_DO_RECEPTOR_SEM_TIPO = "Receptor sofrendo"
PORQUE_DO_RECEPTOR = {
    "teclado": "Teclas ficaram apertadas sozinhas: possível interferência no receptor 2.4G.",
    "mouse": "O mouse falhou no meio do movimento: possível interferência no receptor 2.4G.",
}
PORQUE_DO_RECEPTOR_SEM_TIPO = "O receptor 2.4G falhou: possível interferência."


def dica_do_receptor(tipo: str, texto: str, quando: str) -> Dica:
    """O receptor 2.4G que sofre («3 teclas presas em 1 h»): o mesmo botão do teclado no hub."""
    return Dica(
        chave=f"receptor-sofrendo:{tipo}", icone=ICONE_TECLADO,
        titulo=limitar_o_titulo(TITULO_DO_RECEPTOR.get(tipo, TITULO_DO_RECEPTOR_SEM_TIPO)),
        nivel=AJUSTE,
        acao=Acao(MAPA, ROTULO_VER_NO_MAPA, href=PAGINA_DO_MAPA),
        porque=uma_frase(PORQUE_DO_RECEPTOR.get(tipo, PORQUE_DO_RECEPTOR_SEM_TIPO)),
        detalhe=f"{texto} {quando}".strip())


def montar(dicas: Iterable[Dica], certos: Sequence[str] = ()) -> Painel:
    """Os que mais pesam primeiro (o nível, depois a ordem em que chegaram); as caladas no fim."""
    todas = list(dicas)
    ordenadas = sorted(
        range(len(todas)),
        key=lambda i: (todas[i].calada, -todas[i].peso, i))
    pela_ordem = [todas[i] for i in ordenadas]
    return Painel(
        visiveis=tuple(pela_ordem[:CARTOES_VISIVEIS]), demais=tuple(pela_ordem[CARTOES_VISIVEIS:]),
        certos=tuple(dict.fromkeys(c for c in certos if c)))


__all__ = [
    "AJUSTE",
    "CARTOES_VISIVEIS",
    "DA_CONFERENCIA",
    "DA_ORDEM",
    "GRAVE",
    "MAPA",
    "MOVER",
    "NADA_A_MUDAR",
    "NOTA",
    "PALAVRAS_NO_TITULO",
    "Acao",  # (noqa-acento): chave de máquina
    "Dica",
    "Movimento",
    "Painel",
    "dica_da_conferencia",
    "dica_da_ordem",
    "dica_do_movimento",
    "dica_do_receptor",
    "dica_do_wifi",
    "limitar_o_titulo",
    "montar",
    "o_que_esta_certo",
    "uma_frase",
]
