#!/usr/bin/env python3
"""O pacote da aba `02` Controles — a mais servida das dez, e o MOLDE.

Ela já pintava antes deste despachante: o `controles_vivos.py` monta o pacote
dela desde 30/08, e é de lá que este arquivo tira o que sabe. O que muda é o
ENDEREÇO do conhecimento — ele sai do piloto e vira uma função com contrato, do
mesmo formato das outras nove.

TUDO O QUE ESTA ABA MOSTRA TEM DONO, e é por isso que ela foi a primeira a
viver: `inputs` (os dois analógicos, os gatilhos, os botões), `audio` (o
microfone e o alto-falante, com posse e mudo), `lightbar_rgb`, `player`,
`battery_pct`, `transport` e `vpad_backend`. Zero `sem_dono`.
"""
from __future__ import annotations

from . import Contexto, registrar


@registrar("02-controles.html")
def pacote(ctx: Contexto) -> dict:
    """Os valores da aba Controles, com os nomes que a página tem.

    O DESENCONTRO ERA DE PONTUAÇÃO E DE SENTIDO. O pacote emitia `mic_mudo` com
    underscore e a página tem `mic-selo` com hífen; emitia `mascara` valendo
    `uhid` — o BACKEND — e a página mostra "DualSense", que é o nome da máscara.
    Dez chaves emitidas, uma casando. Medido em 01/09/2026.
    """
    import mesa_viva

    cards = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        e = c.get("inputs") or {}
        a = c.get("audio") or {}
        sp = c.get("speaker") or {}
        rgb = c.get("lightbar_rgb") or []
        casa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})

        # O MUDO TEM TRÊS CARAS, e o selo da tela diz qual: mudo pelo aparelho,
        # mudo pedido pelo Hefesto, e sem posse (o kernel manda).
        mudo = bool(a.get("mic_mudo"))
        posse = a.get("mic_mudo_desejado") is not None
        cards[uniq] = {
            "bateria": f"{c.get('battery_pct')}%" if c.get("battery_pct") is not None else "—",
            "via": (c.get("transport") or "").upper(),
            # A MÁSCARA É O NOME QUE O JOGO VÊ, e a tradução já tem dono em
            # `mesa_viva.NOME_DA_MASCARA`. `uhid` é o backend, e é outra coisa.
            "mascara": casa.get("mascara")
                       or mesa_viva.NOME_DA_MASCARA.get(c.get("vpad_backend") or "", "—"),
            "luz-hex": "#{:02X}{:02X}{:02X}".format(*rgb[:3]) if len(rgb) >= 3 else "—",
            "mic-selo": "MUDO" if mudo else "ATIVO",
            "mic-modo": "" if posse else "sem posse",
            "alto-estado": "Mudo" if sp.get("muted") else f"{sp.get('volume', 0)}%",
            "touch-estado": "Sem toque",
            "l2": e.get("l2_raw"), "r2": e.get("r2_raw"),
        }
    return {"cards": cards, "sem_dono": {},
            "cobertura": {"pintados": sum(len(v) for v in cards.values()), "sem_dono": 0}}


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao aparelho
# ---------------------------------------------------------------------------
# ESTA ABA TEM OITO BOTÕES POR CONTROLE e só TRÊS deles têm dono no daemon. O
# resto desta seção é sobre os cinco que não têm, porque é aí que uma tela
# mente: o botão que responde calado deixa quem clicou concluir que funcionou.
#
# O QUE TEM DONO, medido nos 39 métodos do `ipc_server` em 01/09/2026:
#
#   🎙  data-mudo="microfone"      `mic.set`      (ipc_handlers.py:4755)
#   ♪   data-mudo="alto-falante"   `speaker.set`  (ipc_handlers.py:4589)
#   Sons do jogo  data-rota="jogo" `speaker.set`  com `rota`, o mesmo :4589
#
# O QUE NÃO TEM, e o motivo de cada um está no `sem_dono` do gesto que o recusa
# ou na conferência abaixo:
#
#   Giroscópio / Acelerômetro   não há método de sensor nos 39. O `sensor_hub`
#                               só LÊ, e `profiles/schema.py:902` diz que os
#                               dois estão "FORA POR AUSÊNCIA, NÃO POR DECISÃO",
#                               com dona declarada (`ONDA-CONTROLES-07`).
#   Virtual / Nativo            o modo do microfone é a `ONDA-CONEXOES-06`, e
#                               ela não virou código: `grep` por mic virtual em
#                               `src/` devolve ZERO — só a sprint.
#   Todo o som do PC            metade dele é `pactl set-default-sink`, que não
#                               é IPC. Ver o gesto `rota`.
#   Calibrar / Mapa do Controle são `<a href>`, navegação — não IPC.
#
# NADA SE REESCREVE: o `p` é `pacotes/ponte.py`, que expõe o `app/ipc_bridge.py`
# — a mesma camada que a GUI estável usa, com o payload montado e a recusa do
# daemon traduzida.
#
# O NÚMERO DA ROTA NÃO SE DIGITA. Ele é o `OUTPUT_PATH_SEL` (bits 4-5 do
# `common[7]`) e tem dono nomeado em `core/ds_output_report.py:136`, que é
# módulo puro — o outro lugar onde ele aparece com nome é
# `app/widgets/controller_card.py:716`, e aquele importa GTK.
from hefesto_dualsense4unix.core.ds_output_report import (  # noqa: E402
    SAIDA_L_FONE_R_ALTO_FALANTE,
)

from . import gesto  # noqa: E402


def _uniq(o: dict) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa.

    `""` NÃO vira "todos": um mudo sem dono calaria os quatro controles da mesa
    em vez de um. É o mesmo cuidado que a cura de 04/08/2026 pôs no seletor de
    canal da GUI estável, e a razão está escrita lá — *"com dois cards na tela,
    clicar no card do Controle 2 escrevia no Controle 1"*.
    """
    return str(o.get("uniq") or "")


def _volume_conhecido(dele: dict) -> dict:
    """`{"volume": N}` quando o daemon sabe o número, `{}` quando não sabe.

    ELE NÃO SE INVENTA, e a razão é do aparelho: o DualSense **não devolve** o
    registrador de volume, então `daemon.state_full` só publica a chave
    `speaker` depois do primeiro `speaker.set` (`ipc_handlers.py:4600`). Mandar
    um número de palpite tomaria a posse com o valor errado.

    E MANDÁ-LO QUANDO SE SABE É O QUE A GUI ESTÁVEL FAZ, pela cura de
    04/08/2026 (`controller_card.py:4265`): *"reafirmá-lo aqui é dizer ao
    firmware o mesmo que a tela mostra, em vez de deixá-lo adivinhar"*.
    """
    v = (dele.get("speaker") or {}).get("volume")
    return {"volume": int(v)} if isinstance(v, int) and not isinstance(v, bool) else {}


@gesto("02-controles.html", "mudo")
def mudo(ctx: Contexto, o: dict, p) -> None:
    """O 🎙 e o ♪ — os dois botões de calar, e eles ALTERNAM o que a tela mostra.

    UM GESTO PARA OS DOIS porque a página os marca com o mesmo `data-mudo`, e o
    valor dele diz qual. Separá-los em dois nomes inventaria um vocabulário que
    o desenho não tem.

    **São métodos diferentes, e não é detalhe.** O `mic.set` é o MUDO NO
    FIRMWARE (camada 3, `ipc_handlers.py:4755`): é o único que apaga a luz
    vermelha do plástico, e a partir dele o botão físico do controle deixa de
    valer — é o que o `title` do desenho já promete. O `speaker.set` manda ZERO
    ao alto-falante guardando o volume preferido (`ipc_handlers.py:4589`).
    Trocar um pelo outro calaria a coisa errada.

    ALTERNAR EXIGE LER O ESTADO, e ele vem do daemon, nunca de memória nossa:
    `audio.mic_mudo` é LEITURA do byte que vem em todo report de input, e
    `speaker.muted` é o que nós mandamos (o aparelho não devolve). Guardar o
    valor enviado como se fosse leitura é o hábito que o `ipc_bridge.py:1082`
    nomeia como o que *"fez a tela parecer mentirosa quando ela nunca mentiu"*.

    `mic_set(False)` NÃO devolve a posse ao `hid-playstation` — isso é
    `mic_set(None)`, que era o botão "Liberar" que ela mandou tirar em 30/08
    (*"o botão do Controle sempre controla a interface"*). Aqui só se alterna
    entre calado e ativo, que é o que os dois estados do selo dizem.
    """
    uniq, qual = _uniq(o), str(o.get("mudo") or "")
    if not uniq:
        raise ValueError("mudo: o clique não disse em qual controle")
    dele = ctx.por_uniq(uniq)

    if qual == "microfone":
        # A LEITURA DO FIRMWARE, não o desejo: `mic_mudo` é o que está valendo
        # no plástico agora, e é o que o selo ATIVO/MUDO mostra ao lado.
        agora = bool((dele.get("audio") or {}).get("mic_mudo"))
        if not p.mic_set(not agora, uniq=uniq):
            raise RuntimeError(
                "o daemon não confirmou o mudo do microfone — ou o Hefesto está "
                "parado, ou este controle saiu da mesa")
        return

    if qual == "alto-falante":
        alto = dele.get("speaker") or {}
        # O VOLUME VAI JUNTO QUANDO SE SABE, e a razão é uma recusa do daemon,
        # não zelo: `speaker.set {muted}` sem volume conhecido é ERRO
        # (`ipc_handlers.py:4682`), porque mudo como primeira escrita tranca o
        # alto-falante em zero e o próprio mudo não o solta. O desenho já apaga
        # o botão nesse estado (`alto_pode` do `aba02.py`); esta linha é a
        # segunda trava, para o clique que chegar mesmo assim.
        if not p.speaker_set(muted=not bool(alto.get("muted")), uniq=uniq,
                             **_volume_conhecido(dele)):
            raise RuntimeError(
                "o daemon não confirmou o mudo do alto-falante. Se o volume "
                "deste controle ainda é desconhecido, ele recusa de propósito: "
                "calar antes de saber o volume tranca o alto-falante em zero")
        return

    raise ValueError(f"mudo: não sei calar {qual!r} — a página manda 'microfone' "
                     f"ou 'alto-falante'")


@gesto("02-controles.html", "rota")
def rota(ctx: Contexto, o: dict, p) -> None:
    """Onde o som do controle sai. **"Sons do jogo" tem dono; "Todo o som do PC" não.**

    "SONS DO JOGO" É UM BYTE, e ele é o caso que ela descreveu com o Zelda —
    *"o speaker do controle faz os barulhos da espada do Link enquanto na tela
    tem o som normal do jogo"*. É o `OUTPUT_PATH_SEL` = 2: canal esquerdo para o
    fone/TV, direito para o alto-falante do controle. O `speaker.set` leva a
    `rota` (`ipc_handlers.py:4626`) e a GUI estável manda exatamente isto
    (`controller_card.py:4271`).

    "TODO O SOM DO PC" SÃO DUAS CAMADAS, E A SEGUNDA NÃO É IPC. O
    `profiles/schema.py:516` já escreve o limite com todas as letras:

        LIMITE DECLARADO: a rota é a CAMADA 2 (o firmware). O estado "Todo o
        som do PC" da janela também mexe na CAMADA 1 (o *default sink* do
        PipeWire), que é um fato GLOBAL do sistema (…)

    E `controller_card.py:4218` diz quem vence: *"A camada 1 vence a camada 2:
    volume e rota perfeitos num sink mudo é trabalho invisível."* Quem executa a
    camada 1 é `app/audio_saida.RotaDeSaida.mandar_para_o_controle` (`:820`),
    que roda `pactl set-default-sink` — não há método no daemon para isso, e não
    poderia haver sem inventá-lo.

    ENTÃO ELE RECUSA DIZENDO, em vez de mandar só a metade que dá. Mandar
    `rota=3` sozinho escreveria o byte certo e não moveria uma nota de som: o PC
    continuaria tocando no alto-falante da TV, e a tela teria acendido o botão.
    É a forma exata do defeito que esta casa chama de *ausência de notícia lida
    como sucesso* — e o `--prova-gesto` daria verde por cima dele.

    O que falta para ligá-lo NÃO é código novo de protocolo: é dar à janela nova
    o dono da camada 1 que a janela velha injeta no card
    (`controller_card.definir_pedido_de_rota`, `:4310`). Enquanto isso não
    existir, este botão é honesto ao recusar.
    """
    uniq, qual = _uniq(o), str(o.get("rota") or "")
    if not uniq:
        raise ValueError("rota: o clique não disse em qual controle")

    if qual == "pc":
        raise RuntimeError(
            "'Todo o som do PC' ainda não tem dono nesta janela: metade dele é "
            "a saída padrão do PipeWire (pactl set-default-sink), que não é IPC "
            "— o daemon só faz a camada 2, o byte do firmware. Mandar só ela "
            "acenderia o botão sem mover som nenhum.")

    if qual != "jogo":
        raise ValueError(f"rota: não conheço a rota {qual!r} — a página manda "
                         f"'jogo' ou 'pc'")

    if not p.speaker_set(rota=SAIDA_L_FONE_R_ALTO_FALANTE, uniq=uniq,
                         **_volume_conhecido(ctx.por_uniq(uniq))):
        raise RuntimeError(
            "o daemon não confirmou a rota do alto-falante — ou o Hefesto está "
            "parado, ou este controle saiu da mesa")


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
PONTE = {"mic_set", "speaker_set"}
#: VAZIO, e o vazio é uma AFIRMAÇÃO: os dois métodos desta aba têm função no
#: `ipc_bridge`, então nenhum gesto precisa do degrau cru do `p.chamar`.
METODOS: set[str] = set()


#: O QUE ESTA ABA DECLARA À RÉGUA. O piso e as provas moram AQUI, e não no
#: arquivo de teste, para que ligar uma aba não exija editar um arquivo que oito
#: pessoas editariam ao mesmo tempo.
PAGINA = "02-controles.html"
#: DOIS GESTOS, TRÊS BOTÕES: o `mudo` atende o 🎙 e o ♪, que a página marca com
#: o mesmo `data-mudo`. O piso conta GESTOS porque é o que o despachante
#: registra — a cobertura por botão está nas PROVAS abaixo, que são três.
PISO_DA_ABA = 2
PROVAS = [
    # O 🎙 — e o `True` é o ALTERNAR: o controle da régua vem com `audio: {}`,
    # logo não está mudo, logo o clique manda calar.
    {"pagina": PAGINA, "gesto": "mudo", "clique": {"mudo": "microfone"},  # (noqa-acento) id
     "chama": [("mic_set", [True], {"uniq": "aa:bb:cc:00:00:01"})]},
    # O ♪ — SEM `volume` no payload, e isso é o contrato: o controle da régua
    # vem com `speaker: {}`, que é o estado real de quem nunca recebeu um
    # `speaker.set`. Inventar um número aqui esconderia a recusa do daemon.
    {"pagina": PAGINA, "gesto": "mudo", "clique": {"mudo": "alto-falante"},  # (noqa-acento) id
     "chama": [("speaker_set", [], {"muted": True, "uniq": "aa:bb:cc:00:00:01"})]},
    # "Sons do jogo" — a rota sai da constante, nunca do número digitado.
    {"pagina": PAGINA, "gesto": "rota", "clique": {"rota": "jogo"},  # (noqa-acento) id
     "chama": [("speaker_set", [],
                {"rota": SAIDA_L_FONE_R_ALTO_FALANTE, "uniq": "aa:bb:cc:00:00:01"})]},
]
