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
        pct = c.get("battery_pct")
        cards[uniq] = {
            "bateria": f"{pct}%" if pct is not None else "—",
            # A BARRA, e ela precisa do NÚMERO CRU: o `escrever` do piloto com
            # `data-hef-alvo="largura"` monta `width: <t>%`, e um "95%" ali
            # viraria `width: 95%%`. Zero quando o daemon não sabe — deixar a
            # barra na largura que o gerador desenhou seria a tela afirmando uma
            # carga que ninguém mediu.
            "bateria-barra": int(pct) if isinstance(pct, int) and not isinstance(pct, bool)
                             else 0,
            "via": (c.get("transport") or "").upper(),
            # A MÁSCARA É O NOME QUE O JOGO VÊ, e a tradução já tem dono em
            # `mesa_viva.NOME_DA_MASCARA`. `uhid` é o backend, e é outra coisa.
            "mascara": casa.get("mascara")
                       or mesa_viva.NOME_DA_MASCARA.get(c.get("vpad_backend") or "", "—"),
            "luz-hex": "#{:02X}{:02X}{:02X}".format(*rgb[:3]) if len(rgb) >= 3 else "—",
            "mic-selo": "MUDO" if mudo else "ATIVO",
            # O `mic-modo` SAIU DAQUI EM 01/09/2026, e ele APAGAVA DOIS BOTÕES.
            # O endereço `data-campo="mic-modo"` não era uma folha: era o
            # `<span class="rota mic-modo">` que ENVOLVE o Virtual e o Nativo. O
            # `escrever` do piloto faz `el.textContent = t`, e `t` de um valor
            # vazio é `—` (`hefesto_vivo.py:100-116`) — o primeiro tique trocava
            # os dois botões por um travessão.
            # MEDIDO no Chrome headless, sobre a página publicada, com os dois
            # valores que esta linha emitia (`''` e `'sem posse'`):
            # `[data-mic-modo]` antes **4**, depois **0**, nos dois casos.
            # ERA A CAUSA DE ELES NÃO TEREM DONO: a primeira leva os deixou de
            # fora por "não há método", e a segunda mediu que, além disso, eles
            # nem existiam quando ela clicava. O `data-campo` saiu do gerador
            # junto com esta linha, e há régua nos dois lados.
            # O QUE SE PERDEU: o "sem posse" (`mic_mudo_desejado is None`, o
            # estado em que o botão do plástico ainda manda no mudo). Ele não
            # tinha lugar no desenho — estava sendo escrito por cima dos botões,
            # não num campo dela. Dar-lhe um lugar é decisão dela, não daqui.
            "alto-estado": "Mudo" if sp.get("muted") else f"{sp.get('volume', 0)}%",
            "touch-estado": "Sem toque",
            "l2": e.get("l2_raw"), "r2": e.get("r2_raw"),
        }
    return {"cards": cards, "sem_dono": {},
            "cobertura": {"pintados": sum(len(v) for v in cards.values()), "sem_dono": 0}}


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao aparelho
# ---------------------------------------------------------------------------
# ESTA ABA TEM OITO BOTÕES POR CONTROLE. Eram TRÊS com dono depois da primeira
# leva; são CINCO desde 01/09/2026 — o Virtual e o Nativo entraram. O resto
# desta seção é sobre os três que continuam sem, porque é aí que uma tela mente:
# o botão que responde calado deixa quem clicou concluir que funcionou.
#
# O QUE TEM DONO, medido nos 39 métodos do `ipc_server` em 01/09/2026:
#
#   🎙  data-mudo="microfone"      `mic.set`      (ipc_handlers.py:4755)
#   ♪   data-mudo="alto-falante"   `speaker.set`  (ipc_handlers.py:4589)
#   Sons do jogo  data-rota="jogo" `speaker.set`  com `rota`, o mesmo :4589
#   Virtual / Nativo  data-mic-modo  `machine.declare` (ipc_handlers.py:5258)
#
# O "VIRTUAL / NATIVO" GANHOU DONO EM 01/09/2026, E A AFIRMAÇÃO ANTERIOR CAIU.
# Aqui estava escrito, e é uma frase minha, da primeira leva:
#
#     "Virtual / Nativo — o modo do microfone é a `ONDA-CONEXOES-06`, e ela não
#      virou código: `grep` por mic virtual em `src/` devolve ZERO — só a sprint."
#
# A SEGUNDA METADE CONTINUA VERDADEIRA: `integrations/microfone_do_dualsense.py`
# não existe, e a `ONDA-CONEXOES-06` não virou código. A CONCLUSÃO é que estava
# errada — eu procurei pela PALAVRA "virtual", que é vocabulário do desenho, e
# não pela COISA que os dois botões descrevem. A coisa tem dono desde 22/08/2026
# e é a ponte de microfone por Bluetooth (`QUATRO-MICROFONES-01`, decisão dela:
# *"por controle"*), com o gesto vivo na GUI estável
# (`app/actions/config/secao_controles.py:1113`). Ver o gesto `mic-modo`.
#
# O QUE NÃO TEM, e o motivo de cada um está no `sem_dono` do gesto que o recusa
# ou na conferência abaixo:
#
#   Giroscópio / Acelerômetro   não há método de sensor nos 39 (medido de novo
#                               em 01/09: `daemon.metodos()` não traz um único
#                               `sensor.*`, `gyro.*` nem `motion.*`). O
#                               `sensor_hub` só LÊ — as suas 15 funções são
#                               `leitura`, `reconciliar`, `_abrir_*`, e nenhuma
#                               liga ou desliga nada. `profiles/schema.py:902`
#                               diz que os dois estão "FORA POR AUSÊNCIA, NÃO
#                               POR DECISÃO", com dona declarada
#                               (`ONDA-CONTROLES-07`, que traria a
#                               `ProfileSensorsConfig` — `grep` por ela em
#                               `src/` devolve UMA linha, e é aquele comentário).
#                               O rascunho também não os conhece:
#                               `ipc_draft_applier.py` não tem uma ocorrência de
#                               giro, sensor ou accel.
#   Todo o som do PC            metade dele é `pactl set-default-sink`, que não
#                               é IPC. Ver o gesto `rota`.
#   Calibrar / Mapa do Controle são `<a href>`, navegação — não IPC.
#   Os dois deslizantes de volume   NÃO EXISTEM como elemento clicável. Medido
#                               em 01/09/2026: `type="range"` aparece **zero**
#                               vez nos 16 HTML de `layout/`. O que o desenho
#                               tem é `<span class="trilho"><span class="cheio"
#                               style="width:N%">` — pintura, sem `value` e sem
#                               nenhum `data-*`, logo o `closest` do ouvinte
#                               (`hefesto_vivo.py:204`) nem dispara.
#                               O DAEMON ATENDE OS DOIS (`mic.volume.set` e
#                               `speaker.set {volume}`, e a ponte tem
#                               `mic_volume_set`/`speaker_set`): o que falta é
#                               do lado do DESENHO, e desenho é dela.
#
# NADA SE REESCREVE: o `p` é `pacotes/ponte.py`, que expõe o `app/ipc_bridge.py`
# — a mesma camada que a GUI estável usa, com o payload montado e a recusa do
# daemon traduzida.
#
# O NÚMERO DA ROTA NÃO SE DIGITA. Ele é o `OUTPUT_PATH_SEL` (bits 4-5 do
# `common[7]`) e tem dono nomeado em `core/ds_output_report.py:136`, que é
# módulo puro — o outro lugar onde ele aparece com nome é
# `app/widgets/controller_card.py:716`, e aquele importa GTK.
#
# `secao_controles` É A REGRA DO MICROFONE E AS TRÊS FRASES DELA, do produto
# estável. O guia manda desconfiar de `app/actions/*` — mas o aviso de lá é
# sobre os MIXINS GTK (`self._get`, `self._toast_light`), e `pode_ligar_o_mic` e
# `dica_do_microfone` são funções de MÓDULO, puras, sobre um objeto de dados.
# Medido em 01/09/2026: o import roda sem display e sem `gi` (o `from
# gi.repository import Gtk` daquele arquivo mora DENTRO dos construtores de
# widget). Reescrevê-las seria a segunda verdade: a condição "só no rádio" e a
# frase que a explica já existem, com dono, e são exatamente o que este botão
# precisa dizer quando recusa.
#
# `norm_mac` é o dono da CHAVE do `maquina.json` — doze hex minúsculos. O daemon
# publica o `uniq` ora com dois-pontos, ora sem, e montar a chave à mão aqui
# gravaria a declaração num controle que não existe.
#
# A ORDEM DESTE BLOCO É A DO `ruff --select I`, não a da leitura: um bloco fora
# de ordem reprova o portão de lint, e é ele que decide a integração.
from hefesto_dualsense4unix.app.actions.config import (  # noqa: E402
    secao_controles as _mic_do_produto,
)
from hefesto_dualsense4unix.core.ds_output_report import (  # noqa: E402
    SAIDA_L_FONE_R_ALTO_FALANTE,
)
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac  # noqa: E402

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


def _resposta(r) -> tuple[bool, str]:
    """`(ok, motivo)` do `machine_declare`, tolerando ponte que devolva só `bool`.

    `ipc_bridge.machine_declare:861` devolve `(ok, motivo)`, com o motivo já
    traduzido para frase de tela (`_MOTIVOS_MAQUINA`) — é ele que faz o botão
    RECUSAR DIZENDO em vez de gravar calado.

    O guarda existe porque o dublê da régua devolve `True` para todo nome que
    não seja `identity…_set`: desempacotar às cegas levantaria `TypeError`
    DENTRO do teste, e o instrumento reprovaria a si mesmo em vez de medir o
    botão. É o mesmo `_resposta` que a Conexões e a Sistema já têm — três
    cópias de sete linhas, e a única alternativa seria pôr a função no
    `pacotes/ponte.py`, que é território de ninguém nesta leva.
    """
    if isinstance(r, tuple):
        ok, motivo = [*r, None, None][:2]
        return bool(ok), str(motivo or "")
    return bool(r), ""


def _como_o_produto_ve(ctx: Contexto, uniq: str):
    """O controle na forma que `pode_ligar_o_mic` e `dica_do_microfone` leem.

    Os quatro campos são os do `DadosDoControle` da GUI estável, e cada um sai
    de uma medição, não de um palpite:

    * `no_cabo` — `transport` do `daemon.state_full` (`"usb"` / `"bt"`), a mesma
      chave que o `mesa_viva.mesa_do_estado:316` já usa nesta janela;
    * `endereco` — o `uniq` normalizado por `core/sysfs_leds.norm_mac`, que é
      **a chave do `maquina.json`** ("doze hex minúsculos por schema",
      `bt_mic.uniqs_declarados`). Ela não se monta à mão: o daemon publica o
      `uniq` ora com os dois-pontos, ora sem, e as duas formas têm de cair na
      mesma chave;
    * `adotado` — `True`, e é afirmação medida: o `state_full["controllers"]`
      sai do `describe_controllers` do controlador de DualSense
      (`ipc_handlers.py:2567`), e cada entrada traz `lightbar_rgb`,
      `player_slot` e `vpad_backend`. Controle externo (8BitDo, Pro) não entra
      por essa porta — ele vem por `controller.list`, que esta aba não lê.
    """
    from types import SimpleNamespace

    dele = ctx.por_uniq(uniq)
    return SimpleNamespace(
        adotado=True,
        no_cabo=str(dele.get("transport") or "").lower() == "usb",
        uniq=uniq,
        endereco=norm_mac(uniq) or "",
    )


@gesto("02-controles.html", "mic-modo")
def mic_modo(ctx: Contexto, o: dict, p) -> None:
    """"Virtual" e "Nativo": por onde o som do microfone deste controle chega ao PC.

    O QUE OS DOIS BOTÕES SÃO, e a resposta não estava na palavra "virtual" — a
    primeira leva procurou por ela em `src/`, achou zero, e concluiu que não
    havia dono. A coisa que os `title` do desenho descrevem é a **ponte de
    microfone por Bluetooth**, e ela existe e é dela desde 22/08/2026:

        Virtual  "O Hefesto cria uma fonte de áudio própria e entrega o
                 microfone do controle ao PC por ela."
                 → `integrations/dualsense_bt_audio.py`, que é exatamente isso:
                   Opus tunelado no HID, virando uma fonte do PipeWire.
        Nativo   "O microfone entra como o kernel o expõe, sem o Hefesto no
                 meio."
                 → a ponte no chão. Pelo cabo é o que já acontece: *"por USB o
                   microfone do DualSense é um dispositivo de áudio USB comum e
                   o PipeWire o publica sozinho"* (o cabeçalho daquele módulo).

    QUEM LIGA NÃO É A JANELA, e isso é uma cicatriz, não um detalhe de desenho.
    A GUI estável escreve a DECLARAÇÃO (`machine.declare`) e quem sobe a ponte é
    o daemon; o comentário de `secao_controles.py:1107` diz por quê: *"o
    processo da janela não pode ter esse gesto ao alcance de um clique enquanto
    a posse do hidraw não for arbitrada — o susto de 16/08/2026"*. Aqui é igual:
    este gesto DECLARA, e o `bt_mic` do daemon reconcilia sozinho — a fonte dele
    é **chamável**, relida a cada varredura, e por isso a escolha vale **sem
    reiniciar o daemon** (`daemon/subsystems/bt_mic.py:60`).

    DESLIGAR GRAVA `None`, NUNCA `False`, e a razão é do `utils/maquina.py`:
    *"'nunca pedi' e 'não quero' deixam a ponte no chão do mesmo jeito — e um
    `false` gravado seria um valor de catálogo para o silêncio"*. O `None`
    **sobrescreve** de propósito: `fundir_declaracao:650` declara que *"`None`
    presente na declaração é uma escolha e SOBRESCREVE; só a AUSÊNCIA da chave
    preserva o que havia"*. Sem isso, "Nativo" seria um botão calado.

    NO CABO O "VIRTUAL" RECUSA, e a frase é a do produto — `DICA_MIC_NO_CABO`,
    palavra por palavra. A condição é `pode_ligar_o_mic`, também do produto:
    *"pelo cabo o microfone deste controle é uma placa de som USB e não passa
    por esta ponte — ele já funciona sem ela"*. Deixá-lo gravar ali acenderia o
    botão sem mover uma nota de som, que é o defeito que o gesto `rota` desta
    mesma aba recusa pela mesma razão.

    O "NATIVO" GRAVA NOS DOIS TRANSPORTES, e é diferente de propósito: no cabo
    ele afirma o que já é verdade E deixa escrito que, quando este controle for
    para o rádio, o Hefesto fica fora. É declaração durável, não gesto de
    momento — o `maquina.json` é o que o daemon lê no próximo boot.
    """
    uniq, qual = _uniq(o), str(o.get("micModo") or "")
    if not uniq:
        raise ValueError("mic-modo: o clique não disse em qual controle")
    if qual not in ("virtual", "nativo"):
        raise ValueError(f"mic-modo: não conheço o modo {qual!r} — a página "
                         f"manda 'virtual' ou 'nativo'")

    dados = _como_o_produto_ve(ctx, uniq)
    if not dados.endereco:
        raise RuntimeError(_mic_do_produto.DICA_MIC_SEM_ENDERECO)
    if qual == "virtual" and not _mic_do_produto.pode_ligar_o_mic(dados):
        raise RuntimeError(_mic_do_produto.dica_do_microfone(dados))

    ok, motivo = _resposta(p.machine_declare(
        {"controles": {dados.endereco: {
            "microfone": True if qual == "virtual" else None}}}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o modo do microfone")


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
PONTE = {"mic_set", "speaker_set", "machine_declare"}
#: VAZIO, e o vazio é uma AFIRMAÇÃO: os TRÊS métodos desta aba têm função no
#: `ipc_bridge`, então nenhum gesto precisa do degrau cru do `p.chamar`.
METODOS: set[str] = set()

#: O QUE O DAEMON NÃO PUBLICA DE VOLTA — e por isso a tela não pode confirmar
#: sozinha que o gesto pegou.
#:
#: O `machine.declare` está **fora do `daemon.state_full` de propósito**, e o
#: handler diz a razão (`ipc_handlers.py:5301`): *"aquilo é o tique de 20 Hz, e
#: a declaração muda por gesto dela, não por quadro"*. Ele grava em disco
#: (`maquina.json`), e a única confirmação é o `(ok, motivo)` da chamada — que é
#: exatamente por que o gesto levanta com o motivo em vez de voltar calado.
#:
#: CONSEQUÊNCIA NA TELA, e ela é dívida DECLARADA: o botão aceso continua sendo
#: o que o gerador desenhou, porque a pintura do piloto só sabe escrever texto,
#: largura, fundo e `value` (`hefesto_vivo.py:100-116`) — não sabe acender uma
#: classe. Depois de clicar "Nativo", o "Virtual" segue aceso até o gerador
#: rodar de novo. Ligar isso é do PILOTO, que não é território desta aba.
#: TUPLA, e não dicionário com o motivo: as outras cinco abas ligadas declaram
#: assim (`a03`, `a05`, `a08`, `a09`, `a10`) e o piloto faz
#: `set(getattr(mod, "SEM_ECO", ()))` — um dicionário passaria, e seria a sexta
#: gramática para a mesma lista. O motivo fica no comentário, que é onde ele
#: cabe inteiro.
SEM_ECO = ("mic-modo",)


#: O QUE ESTA ABA DECLARA À RÉGUA. O piso e as provas moram AQUI, e não no
#: arquivo de teste, para que ligar uma aba não exija editar um arquivo que oito
#: pessoas editariam ao mesmo tempo.
PAGINA = "02-controles.html"
#: TRÊS GESTOS, CINCO BOTÕES: o `mudo` atende o 🎙 e o ♪ (mesmo `data-mudo`) e o
#: `mic-modo` atende o Virtual e o Nativo (mesmo `data-mic-modo`). O piso conta
#: GESTOS porque é o que o despachante registra — a cobertura por botão está nas
#: PROVAS abaixo, que são quatro.
PISO_DA_ABA = 3
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
    # "NATIVO", e a prova é ele porque o controle da régua está no CABO
    # (`transport: "usb"`, `test_os_botoes_tem_dono.FALSO`). O "Virtual" ali
    # RECUSA — é o `pode_ligar_o_mic` do produto —, e uma prova que exigisse
    # chamada dele estaria pedindo ao botão que mentisse. Quem cobra a recusa é
    # o teste da mordida, e não esta lista.
    #
    # O `None` É O VALOR, E NÃO A AUSÊNCIA: um `{}` aqui passaria com o gesto
    # mandando qualquer coisa. E a CHAVE é o `uniq` sem os dois-pontos — é o que
    # o `norm_mac` devolve, e é a chave que o `maquina.json` tem.
    {"pagina": PAGINA, "gesto": "mic-modo", "clique": {"micModo": "nativo"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"controles": {"aabbcc000001": {"microfone": None}}}], {})]},
]
