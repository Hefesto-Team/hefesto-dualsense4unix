#!/usr/bin/env python3
"""O pacote da aba `04` Iluminação — a que MAIS tem dono das dez.

O QUE O DAEMON DEVOLVE, medido em 01/09/2026 com o DualSense dela no cabo:

    lightbar_rgb       [0, 0, 255]   a cor ACESA agora            ← tem dono
    lightbar_on        bool          a barra está acesa            ← tem dono
    lightbar_source    str           quem pediu a cor              ← tem dono
    lightbar_disputada bool          a Steam abriu o controle      ← tem dono
    player             1             o número, das cinco lâmpadas  ← tem dono
    leds.lightbar_brightness   o brilho, DO PERFIL          ← tem dono

E desde 25/09/2026 (A-04-PERGUNTA-AO-DAEMON-VIVO-01) o daemon publica também:

    brilho_da_barra    0.0-1.0       o brilho em que a cor acendeu ← tem dono
    brilho_das_luzes   "fraco"…      o degrau das luzes de número  ← tem dono

O BRILHO ESTAVA MARCADO "SEM DONO" AQUI, E ERA MEU ERRO — corrigido em
01/09/2026, depois de ela perguntar: *"vc tá corrigindo na origem esses
problemas que tá relatando né?"*. O que estava escrito:

    "o DualSense não tem brilho de barra — o que a tela chama de brilho é a
     SATURAÇÃO da cor enviada (…) um 82% ali é a tela contando uma conta que
     ninguém faz do outro lado."

A frase sobre o APARELHO pode até se sustentar; a conclusão não. O
`profiles/schema.py` tem `LedsConfig.lightbar_brightness: float = 1.0`, com
faixa declarada (`ge=0.0, le=1.0`), e **os 33 perfis dela têm o campo
preenchido**. Havia dono, em disco, o tempo todo — eu perguntei só ao
`state_full` do daemon, que não publica isto, e li a ausência como inexistência.

A distinção que FICA, porque ela muda o que a tela diz: quando o vivo e o disco
discordam, quem manda na tela é o vivo. Desde 25/09/2026 isso vale para o
brilho também: o `state_full` publica o brilho que o merge acendeu
(`brilho_aceso`, `brilho_das_luzes_acesas`), e o perfil em disco é só a queda
quando o daemon não diz.

E O `lightbar_rgb` É **PÓS-ESCALA DE BRILHO** — 03/09/2026, e é fato do
contrato do daemon, não interpretação. Estava escrito lá o tempo todo
(`ipc_handlers._enrich_controllers_per_controller`, "Contrato de cor (D8)")::

    expõe-se UMA cor, a efetiva conhecida (pós-escala de brilho — o
    `_DesiredOutput.led` já é pós-escala; o manager pré-escala na borda)

Esta aba o lia como PRÉ-escala, e a linha que estava aqui — *"é por isso que o
`hex` continua vindo do daemon"* — descrevia o defeito. Com o brilho abaixo de
100% a caixa mostrava uma cor que ela nunca pediu, a marca dos oito tons apagava
em todos e a tira escurecia duas vezes. Quem separa as duas escalas agora é
`cor_escolhida`; ver lá a medição e por que a inversão é uma varredura, não uma
divisão.

O PRODUTO ALCANÇOU A BANCADA no `players` e no `brilho`: a publicação de
02/09/2026 (`70b58116`) levou ao HTML publicado o `data-hef-alvo="largura"` do
trilho e o `data-campo="players"` do `.players`, e os quatro
`data-campo="player-N"` sumiram dos botões nos DOIS lados. A frase que estava
aqui — *"A BANCADA ANDOU E O PRODUTO NÃO"* — caducou no mesmo dia em que foi
escrita; medir vale mais que lembrar.

O QUE AINDA ESPERA A PUBLICAÇÃO é UM par, e é o do `.aceso`: a bancada diz
`data-campo="luz" data-hef-alvo="html"`, o publicado ainda diz
`data-campo="aceso"`. Ver `desenho_da_luz`.

`players` E `brilho-pct` NÃO SÃO ENDEREÇO MORTO — e a régua do mockup diz que
são. Medido em 02/09/2026, com dois controles na mesa e foto lida::

    p1·players     '1 2 3 4' ← ENDEREÇO MORTO      a fileira É pintada: o anel
                                                   do dono trocou do rosa do
                                                   mockup (cosmic-red) para o
                                                   plástico VIVO, na foto
    p2·brilho-pct  '100%'    ← ENDEREÇO MORTO      a largura É escrita; ela
                                                   coincide com o desenho

Nos DOIS o defeito é da régua, e é a mesma família que `_declarado_neste_elemento`
já documenta para os alvos `classe` e `cor`: entre o que o pacote EMITE e o que a
tela MOSTRA há uma tradução, e comparar os dois crus acusa endereço morto sobre o
produto que acertou. No alvo `largura` o `escrever()` faz `el.style.width = t +
'%'` e a régua compara o `100` declarado com o `'100%'` lido; no alvo `html` o
`LER_CAMPOS` cai no ramo padrão e lê `textContent`, então a fileira inteira é
comparada com `'1 2 3 4'`. **RELATADO** — a cura é em `interface/regua_do_mockup.py`
e `interface/hefesto_vivo.py`, fora do território deste arquivo. Emitir `"100%"`
daqui para "curar" o número poria `width:100%%` na tela.

DOIS ENDEREÇOS MORTOS MORRERAM AQUI — 02/09/2026, e o segundo não aparecia em
régua nenhuma::

    recado   emitido num `data-campo="recado"` que NENHUMA das duas páginas
             tem. A régua do mockup varre os endereços do ARQUIVO, e um campo
             emitido sem lugar nenhum não sai em arquivo algum; quem o via era
             o `casamento.py`, que o acusava como o único órfão da aba. A frase
             passou a viajar no `title` das três peças de `luz`, dentro da
             `dica_da_luz`.
    rgb      uma LISTA — e o pintor **pula lista em coluna**
             (`hefesto_vivo.py`, o laço das colunas: *"if(v !== null && typeof
             v === 'object') continue"*). Ele não podia ser pintado nem que a
             página tivesse onde. E o `casamento.py` também não o conta: ele
             filtra `if not isinstance(v, (dict, list))`. Dois instrumentos,
             ponto cego igual. O `hex` já leva a mesma cor na forma que a tela
             mostra.

A `lightbar_disputada` É O VALOR MAIS IMPORTANTE DESTA ABA, e é o que separa
esta tela de uma tela bonita: quando a Steam tem o controle aberto, a cor que o
daemon publica é a **pedida**, não a **acesa**. Pintar o hex sem dizer isso é
afirmar uma cor que pode não estar no plástico — e o produto já sabe a
diferença, é a tela que precisa contá-la.
"""
from __future__ import annotations

import contextlib
from typing import Any

from . import LUGAR_VAZIO, TRAVESSAO, Contexto, perfil, registrar

SEM_DONO: dict[str, str] = {}


def _hex(rgb: Any) -> str:
    """`(0, 0, 255)` → `#0000FF`, e `—` quando não há cor.

    O travessão NÃO é enfeite: é a mesma marca de "não há valor" que os lugares
    vazios usam nas seis abas. Um `#000000` no lugar diria PRETO, que é uma cor.

    ELE SÓ FORMATA — 02/09/2026, e o guarda que estava aqui tinha dono. A linha
    era `if not rgb or len(rgb) < 3: return "—"`, que é o `_rgb3` do
    `interface/cartao_do_controle.py`; o dono público dele é `cor_do_swatch`, e o
    docstring dele diz por que existe: *"Existe como função separada — em vez de
    um ``_rgb3`` repetido em cada chamador (…) com duas leituras do
    ``lightbar_rgb``, as duas abas divergiriam no primeiro caso de borda"*. A
    cópia daqui divergia em dois casos reais: uma lista de QUATRO canais passava
    (o dono recusa, porque está fora do contrato do IPC) e um canal fora de
    0..255 saía cru (o dono grampeia).
    """
    if not rgb:
        return "—"
    return "#{:02X}{:02X}{:02X}".format(*rgb)


NUMEROS = (1, 2, 3, 4)

#:
ANEL_DO_DONO = "players.dono"

#: usa desde 03/09/2026. `escrever()` faz `el.style.setProperty('--plastico', …)`
ALVO_DO_PLASTICO = "plastico"


def endereco_do_anel(n: int) -> str:
    """O endereço do anel do dono do número ``n``, dentro de UMA coluna."""
    return f"{ANEL_DO_DONO}.{int(n)}"


ITEM_DA_TROCA = "troca.item"

CAMPO_DO_DESENHO = "desenho"

ALVO_DO_DESENHO = "atributo"

_PEDE_O_DESENHO = (
    f'data-campo="{CAMPO_DO_DESENHO}"',
    f'data-hef-alvo="{ALVO_DO_DESENHO}"',
    'data-hef-atributo="data-colorway"',
)

_PINTA_O_DESENHO: bool | None = None


def a_pintura_alcanca_o_desenho() -> bool:
    """Dá para pintar o colorway do desenho HOJE, nesta árvore?"""
    global _PINTA_O_DESENHO
    if _PINTA_O_DESENHO is None:
        from hefesto_dualsense4unix.interface import onde

        try:
            pagina = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
        except OSError:
            pagina = ""
        try:
            piloto = (onde.AQUI / "hefesto_vivo.py").read_text(encoding="utf-8")
        except OSError:
            piloto = ""
        _PINTA_O_DESENHO = (all(p in pagina for p in _PEDE_O_DESENHO)
                            and f"alvo === '{ALVO_DO_DESENHO}'" in piloto)
    return _PINTA_O_DESENHO


def colorway_do_aparelho(casa: dict[str, Any]) -> str:
    """O `colorway` daquele controle, ou `""` quando ninguém o leu.

    O `""` É METADE DA REGRA, e é dela: *campo sem informação não mostra nada*.
    O alvo `atributo` APAGA o `data-colorway` num valor vazio, e o desenho cai
    nos `fill` crus do `ds_limpo.svg` — um DualSense sem identidade, que é o
    honesto quando o mapa de canais responde que a cor não se lê naquele
    transporte. Deixar o atributo faria o contrário: manteria o colorway do
    MOCKUP na tela sobre um aparelho que é outro, que é o defeito que esta
    entrega existe para matar.

    NÃO HÁ TABELA NOVA AQUI. `mesa_viva.CORES` já traduziu o código de fábrica
    do broker para o slug do desenho, e a mesa o carrega em `cor`.
    """
    return str(casa.get("cor") or "")
#: `.players .dono{…border:2px solid var(--plastico)}`; sem `--plastico` a
ANEL_INCERTO = "border:2px dashed var(--comment)"


def _tinta(rgb: Any) -> str:
    """A cor da tira NO TOM DESTA JANELA — ou `""`, que quer dizer APAGADA.

    DUAS ESCALAS DA MESMA COR, e a distinção é dela: *"a cor selecionada (…)
    precisa refletir no lightbar."* O `#0000FF` é o que vai ao plástico; o
    `#7EB8D4` é o azul que esta janela desenha, porque a paleta da casa não tem
    azul puro. `monta.tom_da_casa` é o dono da tradução, e é o MESMO que o
    gerador usa para pintar a guia de oito botões — pintar a tira com o hex CRU
    punha na tela uma cor que a guia não mostra em lugar nenhum.

    O `""` NÃO É "sem estilo": ele manda `desenho_da_luz` desenhar a tira
    APAGADA, com estilo explícito. Ver lá o que a ausência custou.
    """
    if not rgb:
        return ""
    import monta

    return str(monta.tom_da_casa(_hex(rgb)))


def chave_do_override(uniq: str) -> str:
    """O `uniq` na forma em que o DISCO guarda a chave de `controllers`.

    UM DONO PARA O ENDEREÇO DO CONTROLE DENTRO DO PERFIL, e ele é o `norm_mac`
    do backend — o MESMO que `profiles/schema._validate_controllers_keys` usa
    para canonizar a chave na entrada. Escrever `d4:2f:…` onde o disco guarda
    `d42f…` criaria um segundo dono para o mesmo controle: o override que ela
    gravou pela tela e o que o backend enumera deixariam de ser o mesmo.

    POR QUE ELE PRECISOU EXISTIR AGORA: até 03/09/2026 esta aba só LIA o
    override (`brilho_do_controle`), e lia com a string crua. Isso funciona na
    mesa dela — medido no daemon vivo, o `state_full` publica
    `uniq='143a9a0000ab'`, já normalizado —, mas não é contrato: o `norm_mac`
    aceita as duas formas justamente porque as duas circulam, e a régua desta
    casa endereça com `aa:bb:cc:00:00:01`. Com o trilho passando a ESCREVER, ler
    numa forma e gravar noutra seria a divergência clássica: o brilho gravado no
    `aabbcc000001` e a coluna imprimindo o global, para sempre.

    `""` VOLTA `""` — quem decide o que fazer sem alvo é quem chamou (`_uniq`,
    que recusa dizendo). Inventar uma chave aqui gravaria no controle errado.
    """
    if not uniq:
        return ""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(uniq) or uniq


def brilho_do_controle(p: dict[str, Any] | None, uniq: str) -> float | None:
    """O brilho da barra DAQUELE controle: o override, ou o do perfil.

    UM DONO, TRÊS CHAMADORES — e é por isso que ele saiu de dentro do `pacote()`
    em 03/09/2026. A conta estava escrita lá e em lugar nenhum mais, porque só a
    PINTURA a fazia; os gestos que ESCREVEM a cor não passavam brilho nenhum, e
    era exatamente esse o defeito (ver `_escrever_a_cor`). Curá-lo com uma
    segunda leitura do mesmo par de campos criaria a divergência clássica: a
    coluna mostrando um número e o fio levando outro, por dois códigos.

    A ORDEM É A DO MERGE, e ela tem dono: `ControllerOverrides.leds` vence o
    `LedsConfig` global — o mesmo que `profiles/schema.py` declara e que o
    backend resolve. Aqui só se lê o que o disco diz; quem resolve as cinco
    camadas é o daemon.

    `None` QUER DIZER "NÃO SEI", e não 1.0. A tela mostra `—` nesse caso, e o
    `led.set` recebe `brightness=None`, que o `_payload_led_set` OMITE do
    payload — o daemon então assume 1.0, que é o retrocompatível. Mandar `1.0`
    daqui diria "ela escolheu cheio" onde ninguém escolheu nada.
    """
    if not isinstance(p, dict):
        return None
    leds = p.get("leds")
    global_ = leds.get("lightbar_brightness") if isinstance(leds, dict) else None
    #: mesa dela (o `state_full` publica `uniq='143a9a0000ab'`, já normalizado)
    alvo = chave_do_override(uniq)
    meu = next((v for k, v in (p.get("controllers") or {}).items()
                if chave_do_override(str(k)) == alvo), None)
    seus = (meu.get("leds") or {}) if isinstance(meu, dict) else {}
    b = seus.get("lightbar_brightness", global_) if isinstance(seus, dict) else global_
    if b is None:
        return None
    try:
        return max(0.0, min(1.0, float(b)))
    except (TypeError, ValueError):
        return None


def brilho_aceso(c: dict[str, Any] | None, p: dict[str, Any] | None,
                 uniq: str) -> float | None:
    """O brilho em que a barra DESTE controle acende agora — pergunte ao daemon vivo.

    A-04-PERGUNTA-AO-DAEMON-VIVO-01, 25/09/2026. O trilho, a caixa `#RRGGBB`,
    a marca da fileira e os gestos de cor liam `brilho_do_controle`, que é o
    DISCO do perfil ativo. A camada da usuária (R-20) atravessa a troca
    AUTOMÁTICA de perfil: medido na mesa de quatro real, o P1 solto a 60% seguia
    aceso a 60% depois do autoswitch para um perfil que diz 82%, e o trilho
    dizia 82% — a tela afirmando um brilho que não está no plástico.

    O DAEMON PUBLICA O QUE O MERGE ACENDEU (`c["brilho_da_barra"]`, do
    `ipc_handlers._brilhos_acesos`), e é o dono. Sem ele — daemon de outra
    versão, a cor que chegou sem brilho, o perfil que não o publicou —, o
    disco, que é o que esta aba respondia antes; não se inventa.

    :param c: a entrada do daemon deste controle (`ctx.por_uniq`), ou `None`.
    :param p: o perfil ativo, CRU (`perfil.ativo`).
    """
    vivo = (c or {}).get("brilho_da_barra")
    if isinstance(vivo, (int, float)) and not isinstance(vivo, bool):
        return max(0.0, min(1.0, float(vivo)))
    return brilho_do_controle(p, uniq)


ENDERECO_DO_AUTOMATICO = "auto-cores"


def automatico_do_perfil(p: dict[str, Any] | None) -> bool:
    """O `leds.auto_player_colors` do perfil ativo — o martelo mais pesado da aba."""
    if not isinstance(p, dict):
        return True
    leds = p.get("leds")
    if not isinstance(leds, dict) or "auto_player_colors" not in leds:
        return True
    return bool(leds.get("auto_player_colors"))


# O INTERRUPTOR CONTINUA COM O NOME DELE em `ENDERECO_DO_AUTOMATICO`, acima —

ROTULO_DO_BRILHO = "Brilho da barra de luz deste controle"

DICA_DO_BRILHO = ("Brilho da barra deste controle. Grava no perfil ao "
                  "soltar — não espera o Salvar Perfil.")


def _com_o_brilho(rgb: tuple[int, int, int], brilho: float) -> tuple[int, int, int]:
    """`rgb` escalado pelo brilho — **pela função do produto**, nunca por conta.

    `core/led_control.LedSettings.apply_brightness` é o dono, e a conta dele
    passa pelo PISO (`fator_do_brilho`, D-2909-O-BRILHO-TEM-PISO): acima de 0 a
    luz nunca sai abaixo do piso. O `_handle_led_set` do daemon e o provider da
    cor automática (D11) chamam o mesmo dono, e é por ser a mesma conta que a
    varredura de `cor_escolhida` pode ser exata. Digitar a multiplicação aqui
    seria uma cópia, e ela envelheceu calada no dia em que o dono ganhou o piso.
    """
    from hefesto_dualsense4unix.core.led_control import LedSettings

    return LedSettings(lightbar=rgb).apply_brightness(brilho).lightbar


#: catorze (HLS, matiz em graus):
#:     azul    #0000FF 240,00° (automático do P1)  vizinho mais perto a 30,12°
FORA_DA_GUIA = ("#0080FF", "#FF00FF", "#000000")


def tons_da_guia() -> tuple[tuple[int, int, int], ...]:
    """Os ONZE tons que a guia desta aba oferece, na ordem do desenho.

    NÃO SE DIGITA NENHUM, e as duas metades têm donos diferentes:

    * os OITO primeiros são `core/led_control.player_slot_color(1..8)` — a mesma
      paleta que acende as cinco lâmpadas e que o daemon usa como cor automática
      de cada número. Eles ficam porque são o atalho para a cor do jogador;
    * os TRÊS seguintes são as chaves que `monta.TOM_DA_CASA` conhece, os oito
      não cobrem e :data:`FORA_DA_GUIA` não tirou.

    ERA OITO ATÉ 09/09/2026, CATORZE ATÉ 11/09/2026. A primeira mudança foi
    decisão dela na bancada (*"adicionamos os tons faltantes pra cada
    controle"*); a segunda é a poda de :data:`FORA_DA_GUIA`, e a razão dela é
    de espaço.

    QUEM FILTRA É ESTA FUNÇÃO, E NÃO O DONO DOS TONS. `monta.TOM_DA_CASA`
    continua conhecendo os catorze e `core/led_control.player_slot_color`
    continua devolvendo os oito: o que mudou é o que a GUIA mostra. Os dois
    estão em `nao_toca` da sprint de propósito — a cor automática de um jogador
    é do daemon, não desta tela.

    ELA RECUSA DIZENDO, e as duas recusas existem porque um erro em
    :data:`FORA_DA_GUIA` seria mudo de outro jeito:

    1. **um hex que não está em `TOM_DA_CASA`** não tira nada — seria uma linha
       morta parecendo decisão;
    2. **um hex que é cor automática de jogador** quebraria o contrato de
       `titulo_da_casa`, que promete *"Cor automática do Player i"* para as
       oito primeiras casas pela POSIÇÃO. Tirar uma da frente faria a nona
       casa dizer o nome da oitava.

    A ORDEM IMPORTA e é esta: quem procura a cor do próprio número a encontra
    onde sempre esteve, e o que é novo entra depois.
    """
    import monta

    from hefesto_dualsense4unix.core.led_control import player_slot_color

    automaticos = tuple(player_slot_color(n) for n in range(1, 9))
    ja_tem = {"#{:02X}{:02X}{:02X}".format(*rgb) for rgb in automaticos}
    fora = {h.upper() for h in FORA_DA_GUIA}
    desconhecidos = sorted(fora - {h.upper() for h in monta.TOM_DA_CASA})
    if desconhecidos:
        raise ValueError(
            "FORA_DA_GUIA cita tom que `monta.TOM_DA_CASA` não conhece e por "
            f"isso não tira nada da fileira: {', '.join(desconhecidos)}")
    automaticos_podados = sorted(fora & ja_tem)
    if automaticos_podados:
        raise ValueError(
            "FORA_DA_GUIA cita cor automática de jogador, e a guia numera as "
            "oito primeiras casas pela posição — a casa seguinte passaria a "
            f"dizer o número da anterior: {', '.join(automaticos_podados)}")
    extras = tuple(
        (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))
        for h in monta.TOM_DA_CASA
        if h not in ja_tem and h.upper() not in fora
    )
    return automaticos + extras


def titulo_da_casa(i: int) -> str:
    """A frase de cada casa da guia. As oito primeiras são cor de número."""
    quem = f"Cor do Player {i}. " if i <= 8 else ""
    return f"{quem}Pinta a barra, não muda o número."


def _acende_em_alguma_intensidade(tom: tuple[int, int, int],
                                  alvo: tuple[int, int, int]) -> bool:
    """`tom`, escalado por algum fator de (0, 1], acende exatamente `alvo`?"""
    from hefesto_dualsense4unix.core.led_control import _escala_crua

    baixo, alto = 0.0, float("inf")
    for c, v in zip(tom, alvo, strict=True):
        if c == 0:
            if v != 0:
                return False
            continue
        baixo, alto = max(baixo, v / c), min(alto, (v + 1) / c)
    if baixo <= 0.0 or baixo >= alto or baixo > 1.0:
        return False
    topo = min(alto, 1.0)
    fator = 1.0 if topo <= baixo else (baixo + topo) / 2
    return _escala_crua(tom, fator) == alvo


def a_casa_da_cor(rgb: Any) -> str | None:
    """A CASA da guia de uma cor pedida: o tom que a acende, ou `None`."""
    if not rgb or len(tuple(rgb)) < 3:
        return None
    r, g, b = tuple(rgb)[:3]
    alvo = (int(r), int(g), int(b))
    if alvo == (0, 0, 0):
        return None
    tons = tons_da_guia()
    if alvo in tons:
        return _hex(alvo)
    casados = [t for t in tons if _acende_em_alguma_intensidade(t, alvo)]
    return _hex(casados[0]) if len(casados) == 1 else None


def a_chave_da_cor(rgb: Any) -> str | None:
    """Onde a cor pousa na mesa das casas: a casa, ou a própria cor sem casa."""
    if not rgb or len(tuple(rgb)) < 3 or tuple(rgb)[:3] == (0, 0, 0):
        return None
    return a_casa_da_cor(rgb) or _hex(tuple(int(c) for c in tuple(rgb)[:3]))


def as_casas_da_mesa(pecas: Any) -> dict[str, list[dict[str, Any]]]:
    """A MESA DAS CASAS: `{casa: [donos na ordem do número]}`, uma vez por tique.

    UMA mesa para as três perguntas — o X, a marca própria e a recusa — que
    liam dois dicionários de um dono por cor (o do X guardava o último, o da
    recusa o primeiro). Duas peças no mesmo tom (o «Todos», ou o global de
    vários) ficam as duas na casa.

    A entrada é dado puro, uma peça por controle — `quem` (o `uniq` no
    produto, o lugar na bancada), `cor`, `nome`, `numero` e `plastico` —, para
    o pacote e a bancada chamarem a mesma função.
    """
    casas: dict[str, list[dict[str, Any]]] = {}
    for peca in sorted(pecas, key=lambda p: int(p.get("numero") or 0)):
        chave = a_chave_da_cor(peca.get("cor"))
        if chave is not None:
            casas.setdefault(chave, []).append(peca)
    return casas


def os_outros_donos(casas: dict[str, list[dict[str, Any]]], chave: str | None,
                    meu: str) -> list[dict[str, Any]]:
    """A pergunta UMA: quem, além deste controle, tem esta casa?"""
    if chave is None:
        return []
    return [d for d in casas.get(chave, ()) if d.get("quem") != meu]


def _os_nomes(donos: list[dict[str, Any]]) -> str:
    """«P2», «P2 e P3», «P2, P3 e P4» — na ordem em que vieram."""
    nomes = [str(d.get("nome") or "") for d in donos if d.get("nome")]
    if len(nomes) <= 1:
        return "".join(nomes)
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


LINHA_INCERTA = ("repeating-linear-gradient(90deg,var(--comment) 0 3px,"
                 "transparent 3px 5px)")


def plastico_da_linha(slug: str) -> str:
    """A tinta do plástico que a linha do dono veste, ou `""` se não se sabe.

    UM DONO, DOIS CHAMADORES: o pacote (`_as_pecas_da_mesa`) e a bancada do
    `aba04.py`. É o casco pelo `cor_de_css` (`_cor_do_plastico`) passado pelo
    piso de contraste do card (`tom_para_a_borda`), o mesmo que a borda da 02
    usa: a linha mora no painel escuro, e o Midnight Black cru sumiria nele.
    """
    from hefesto_dualsense4unix.integrations.cor_do_plastico import tom_para_a_borda

    return tom_para_a_borda(_cor_do_plastico(slug))


def tinta_da_linha(donos: list[dict[str, Any]]) -> str:
    """O valor de `--dono`: a linha embaixo da casa, em partes iguais por dono."""
    def tinta(d: dict[str, Any]) -> str:
        cor = str(d.get("plastico") or "")
        return f"linear-gradient({cor},{cor})" if cor else LINHA_INCERTA

    if len(donos) == 1:
        cor = str(donos[0].get("plastico") or "")
        return cor or LINHA_INCERTA
    n = len(donos)
    return ",".join(
        f"{tinta(d)} {100 * i / (n - 1):.4g}% 0/{100 / n:.4g}% 100% no-repeat"
        for i, d in enumerate(donos))


def fileira_de_tons(meu: str, casas: dict[str, list[dict[str, Any]]],
                    recuo: str = "", *, ligado: bool = True) -> str:
    """Os onze tons de uma coluna, em HTML — o miolo da `.guia`.

    **COR-X-01, decisão dela de 09/09/2026:** *"onde eu escolher uma cor, em
    volta dela fica a borda da cor do plastico do controle e um X na cor
    selecionada por mim de forma que me impeça de setar alguma cor de um
    coleguinha"* <!-- noqa-acento: citação literal -->

    A BORDA VIROU LINHA — D-2909-A-LINHA-DA-COR-DO-DONO, 29/09/2026, pedido
    dela na bancada (*«talvez uma linha abaixo do quadradinho de cada cor
    contendo a cor do plástico daquele controle»*): <!-- noqa-acento: citação literal -->
    toda casa com dono ganha, embaixo, a linha do plástico de quem a usa, nas
    quatro colunas. A tinta vai na própria casa (`--dono`, ver
    `tinta_da_linha`). A borda da escolhida saiu: ela era a cor de texto do
    `<button>` (quase preta, igual nos quatro), e na cor certa ainda sumia no
    Starlight Blue sobre a casa azul e no White sobre a casa branca.

    POR QUE A FILEIRA INTEIRA, e não um endereço por botão — é a mesma razão
    de `fileira_de_players`, um degrau mais funda: **o alvo `classe` do pintor
    compara por IGUALDADE** (`hefesto_vivo.escrever`, ramo `classe`:
    `aceso = (t === quando)`). "Esta cor está na lista das que os OUTROS
    tomaram" não é uma igualdade, e não há `data-hef-quando` que a exprima.
    Quem sabe quem tem qual cor é o pacote, que vê a mesa inteira.

    CADA CASA RESPONDE «de quem é?» pela mesa das casas (`as_casas_da_mesa`),
    e não mais «este hex é de alguém?» — A-PALETA-MARCA-A-COR-DE-CADA-
    CONTROLE-01, 29/09/2026:

    * `on` quando a casa tem este controle;
    * X quando a casa tem outro dono e não tem este. O X é preto com contorno
      branco desde 09/09 (a cor do plástico sumia no tom pastel); no «Todos» a
      casa de todos não ganha X em coluna nenhuma;
    * o `data-gesto` só onde a recusa passa: a casa sem dono e a casa só dele.
      A casa que ele divide com outros (o «Todos», o global num tom) fica `on`,
      sem X e sem gesto, com o `aria-disabled`: a coluna do último dono
      oferecia esse clique, e o botão piscava a recusa;
    * o `title` da casa com dono alheio nomeia os donos: um X mudo obriga ela a
      adivinhar qual dos outros controles está naquele tom;
    * a linha: toda casa com dono, a dele também. A casa dele é a que tem a
      linha da cor da moldura e não tem X.

    :param meu: quem é esta coluna — o `uniq` no produto, o lugar na bancada.
    :param casas: a mesa das casas (`as_casas_da_mesa`), com este controle.
    :param ligado: há controle neste lugar? Um lugar vazio não ganha `on` nem
        X — não há escolha a marcar e não há dono a proteger.
    """
    import monta

    linhas = []
    for i, rgb in enumerate(tons_da_guia(), start=1):
        cru = "#{:02X}{:02X}{:02X}".format(*rgb)
        donos = list(casas.get(cru, ())) if ligado else []
        outros = os_outros_donos(casas, cru, meu) if ligado else []
        dele = len(outros) < len(donos)
        alheia = bool(outros) and not dele
        classes = "tom"
        if dele:
            classes += " on"
        if alheia:
            classes += " tomado"
        if donos:
            classes += " com-dono"
        estilo = f"background:{monta.tom_da_casa(cru)}"
        if donos:
            estilo += f";--dono:{tinta_da_linha(donos)}"
        titulo = _os_nomes(outros) if outros else titulo_da_casa(i)
        # setar alguma cor de um coleguinha"*. <!-- noqa-acento: citação dela -->
        # tinhamos resolvido esse aviso"*. <!-- noqa-acento: citação dela -->
        aberto = ("" if outros else f' data-gesto="cor" data-hex="{cru}"')
        travado = ' aria-disabled="true"' if outros else ""
        linhas.append(
            f'{recuo}<button class="{classes}" style="{estilo}"'
            f'{aberto}{travado} title="{titulo}"></button>')
    return "\n".join(linhas)


def cor_escolhida(efetiva: Any, brilho: float | None) -> Any:
    """A cor que ela PEDIU, a partir da que está ACESA e do brilho.

    O DEFEITO QUE ESTA FUNÇÃO MATA, e ele é do daemon para cima — está escrito
    no contrato dele (`ipc_handlers._enrich_controllers_per_controller`, o
    "Contrato de cor (D8)")::

        expõe-se UMA cor, a efetiva conhecida (PÓS-ESCALA DE BRILHO — o
        `_DesiredOutput.led` já é pós-escala; o manager pré-escala na borda)

    Esta aba lia esse `lightbar_rgb` como se fosse a cor ESCOLHIDA, e com o
    brilho abaixo de 100% isso quebra TRÊS coisas na mesma coluna, todas pela
    mesma raiz — medido em 03/09/2026 com `brilho=0.5` e o azul do P1::

        a caixa `#RRGGBB`   dizia `#00007F`, uma cor que ela nunca pediu
        a marca dos 8 tons  APAGAVA em todos — `data-hef-quando` compara com
                            `#0000FF`, e nenhum dos oito casa com `#00007F`
        a tira              pintava o hex CRU (o `tom_da_casa` só conhece os
                            oito CHEIOS) e ainda aplicava `opacity:0.5` por
                            cima — o brilho escurecendo DUAS vezes

    A CURA É A INVERSÃO PELA FÓRMULA DO PRODUTO, e não uma divisão: dividir
    `127/0.5` dá 254, e a marca continuaria apagada por um. O que se faz é
    aplicar a conta do dono (`_com_o_brilho`) nos OITO tons e ver qual produz a
    cor que está acesa — o mesmo desenho de `lightbar_actions.nome_do_desenho`,
    que varre os oito padrões canônicos para batizar um bitmask.

    QUEM ELA VARRE É `monta.TOM_DA_CASA`, OS CATORZE — e NÃO os onze da guia.
    A diferença nasceu em 11/09/2026, quando :data:`FORA_DA_GUIA` tirou três da
    fileira, e ela é a razão de a varredura ter dono próprio: o que esta função
    inverte é *o que o produto pode ter ACESO*, e não *o que a guia oferece
    HOJE*. Um perfil dela salvo ontem no `#0080FF`, a 50% de brilho, acende
    `#004080`; varrer só os onze devolveria o escuro, e a caixa `#RRGGBB`
    passaria a mostrar uma cor que ela nunca pediu **por causa de uma poda de
    tela**. Poda de guia não pode reescrever o passado do disco dela.

    SEM CASAMENTO, A EFETIVA VOLTA INTEIRA. É o caso de uma cor que não é tom
    da casa — o global do perfil dela (`#2850B4`) — que a 82% acende outro
    hexa, e não há como saber de qual pedido ele veio. Aí a tela mostra o que
    está no plástico, que é o honesto; inventar um pedido seria afirmar uma
    escolha que ninguém fez.

    O PRETO NÃO CASA, E O CASAMENTO TEM DE SER ÚNICO — 24/09/2026,
    A-MARCA-DA-COR-NAO-SOME-01. A varredura devolvia o PRIMEIRO tom que
    casasse, e a 0% os catorze acendem `(0, 0, 0)`: o primeiro da tabela é o
    `#0000FF`, e a coluna de quem ela apagou pelo trilho passava a dizer azul
    — a borda pulava para o azul, o X da cor dele sumia dos outros três, e o
    P1 ganhava um X na PRÓPRIA cor. Medido no piloto, com o clique. A luz
    apagada e a que casa com mais de um tom não dizem de qual pedido vieram
    (ver `_o_tom_que_acende`), e aí a efetiva volta inteira.

    :param efetiva: o `lightbar_rgb` do daemon, ou `None`/vazio quando não há.
    :param brilho: `brilho_aceso`. `None` ou `1.0` devolvem a efetiva sem
        varrer nada — a 100% as duas escalas são a mesma, e varrer só gastaria.
    """
    if not efetiva:
        return efetiva
    if brilho is None or brilho >= 1.0:
        return efetiva
    tom = _o_tom_que_acende(efetiva, brilho)
    return efetiva if tom is None else tom


def _o_tom_que_acende(efetiva: Any,
                      brilho: float | None) -> tuple[int, int, int] | None:
    """O tom da casa que, COM ESTE BRILHO, acende a cor publicada — ou `None`.

    É a varredura de `cor_escolhida`, com a conta do dono (`_com_o_brilho`), e
    ela responde `None` em vez de devolver a efetiva: quem chama precisa saber
    se a luz acesa DISSE a cor ou não, porque é aí que a escada de
    `_a_cor_de_agora` desce um degrau.

    `None` EM TRÊS CASOS, e os dois primeiros o piloto mediu com o clique em
    24/09/2026:

    * **nenhum tom casa** — a luz publicada é de OUTRO brilho. O gesto
      `brilho` grava o número novo no disco antes de o daemon publicar a luz
      nova (o `state_full` guarda a leitura do nó por 1 s), e por meio segundo
      cada tique invertia a luz velha com o brilho novo;
    * **a luz está apagada** — a 0% os catorze tons acendem preto, e acima de
      0% o `#000000` é o ÚNICO que acende preto: subindo o trilho a partir de
      0%, o disco já diz 70% e o daemon ainda publica o preto dos 0%, e a
      coluna inteira virava preta por meio segundo. Luz apagada não diz cor —
      é a ordem dela de 22/09 que `led_control.cor_escolhida` guarda, *o
      preto é banido como cor* —, e quem apagou pelo «Desligar» tem a cor
      dela GRAVADA com o brilho em 0%: é o degrau seguinte da escada que a
      devolve;
    * **mais de um tom casa** — de 0,4% a 0,7% de brilho o vermelho, o rosa
      e o laranja acendem todos `(1, 0, 0)`, e há trios iguais no azul e no
      verde. O trilho anda de 1 em 1% e não chega lá; um perfil gravado por
      outra porta chega, e devolver o primeiro da tabela seria escolher por
      ela.

    A 100% (ou sem brilho) não há conta a desfazer: a luz é o tom se ela for
    um dos catorze.
    """
    import monta

    if not efetiva:
        return None
    r, g, b = (int(c) for c in tuple(efetiva)[:3])
    alvo = (r, g, b)
    if alvo == (0, 0, 0):
        return None
    if brilho is None or brilho >= 1.0:
        return alvo if _hex(alvo) in monta.TOM_DA_CASA else None
    casados = []
    for h in monta.TOM_DA_CASA:
        tom = (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))
        if _com_o_brilho(tom, brilho) == alvo:
            casados.append(tom)
    return casados[0] if len(casados) == 1 else None


TIRA_APAGADA = "background:var(--panel);color:transparent;opacity:1"

ACESA, APAGADA, INCERTA = "acesa", "apagada", "incerta"

ENDERECO_DA_INCERTA = "luz-incerta"

CLASSE_DA_INCERTA = "incerta"


def estado_da_tira(recado: str | None) -> str:
    """Qual dos três estados a tira desenha — **perguntado ao motor**.

    O DISCRIMINADOR É O PRIMEIRO RETORNO de
    `interface/cartao_do_controle.rotulo_lightbar`, e não o segundo: a docstring
    dele diz que a cor devolvida é *"a BASE do accent"*, e ela vem PREENCHIDA
    no ramo em que o próprio motor avisa que a cor pode não estar no plástico
    (a Steam). Ler a base como "há luz?" colapsa dois estados — é o mesmo
    defeito que a `a02_controles` mediu com sonda em 02/09/2026.

    ONDE CAI CADA UM DOS QUATRO RAMOS do motor (`controller_card.rotulo_lightbar`)::

        (None, rgb)                        cor conhecida e acesa      → acesa
        "Lightbar: apagada"                fonte NOSSA, desligada     → apagada
        "A Steam tem este controle aberto" quem segura o `fd`         → incerta
        "Lightbar: cor desconhecida"       sem fonte, ou sem rgb      → incerta

    O MODO NATIVO NÃO É RAMO desde 24/09/2026
    (`D-2409-NO-NATIVO-A-TELA-MOSTRA-A-COR`): no Nativo a barra é do Hefesto, e
    a tira desenha a cor como em todo modo, em vez do tracejado.

    A FRASE DA APAGADA NÃO SE DIGITA — ela se PERGUNTA. Das quatro que
    `rotulo_lightbar` devolve só uma é constante exportada
    (`ROTULO_LIGHTBAR_SEGURADA`), e `a02_controles.ROTULO_DA_LUZ_APAGADA` já
    resolveu isto para a aba irmã: perguntar ao motor com a entrada mínima que
    só o ramo "apagada" atende. **Reusar é o contrário de copiar** — uma segunda
    derivação aqui envelheceria calada no dia em que o motor trocasse a frase, e
    esta aba voltaria a colapsar "apagada" com "não sei" sem régua reprovar.
    """
    from .a02_controles import ROTULO_DA_LUZ_APAGADA

    if recado is None:
        return ACESA
    return APAGADA if recado == ROTULO_DA_LUZ_APAGADA else INCERTA


def o_coop_manda(state: dict[str, Any]) -> bool:
    """O co-op está DE FATO numerando mais de um controle?

    NÃO se lê `coop.enabled`, e a razão está MEDIDA no motor:
    `app/actions/status_actions.texto_do_coop_derrubado` diz, com todas as
    letras, que *"``CoopManager.disable()`` não zera ``coop_enabled``, então o
    ``state_full`` segue publicando ``coop.enabled=True`` com ``coop.players=1``
    — de fora, indistinguível de 'ela desligou o co-op'"*. Medido na mesa de
    02/09/2026, com o co-op parado e dois controles ligados::

        "coop": {"enabled": true, "players": 1, "mesa": [ … uma entrada … ]}

    Quem manda nas cinco lâmpadas é a CAMADA de co-op do merge
    (`core/backend_pydualsense._merged_desired_for_key`, a segunda de cinco), e
    ela só tem opinião quando há mais de um jogador. Ler o booleano mandaria o
    `player` pedir um `coop.sync` inútil numa mesa de um jogador só, e deixaria
    sem escrever o override que é quem acende ali (`_acender_o_numero`).

    MEDIDO EM 25/09/2026 (O-CO-OP-LOCAL-SAI-01), e o ramo continua de pé: a
    camada existe (`backend_pydualsense._desired_coop_by_uniq`) e quem a publica
    é o PRÓPRIO Hefesto (`CoopManager._apply_coop_player_leds`, só com um
    secundário ou mais, que é `players > 1`), com o número da mesa. O co-op não
    é um modo que se liga (`D-2409-O-CO-OP-LOCAL-SAI`); esta função responde
    «há mais de um jogador», e é só isso que o nome dela quer dizer.
    """
    coop = state.get("coop")
    if not isinstance(coop, dict):
        return False
    try:
        return int(coop.get("players") or 0) > 1
    except (TypeError, ValueError):
        return False


def dica_da_luz(nome: str, via: str, recado: str) -> str:
    """A dica da célula LEDs: o controle VIVO, e só o que este pacote MEDE.

    DUAS DECISÕES DELA, de 02/09/2026, e esta função é as duas::

        7. "a palavra ACESO sai do texto"
        8. "a interface mostra o que tá conectado e não o controle do mockup"

    O que estava cravado no desenho — e portanto na tela dela — era::

        title="O Cosmic Red aceso: as duas tiras na cor escolhida, e as cinco
               lâmpadas no padrão do Player 1."

    Duas afirmações, as duas erradas ao mesmo tempo. **O nome** era o do mockup:
    com o controle de hoje na mesa, a MESMA coluna escreve `P1 • White • USB`
    no rótulo e `Cosmic Red` na dica, dez pixels abaixo. **E a palavra `aceso`**
    afirma um estado do aparelho que ninguém pode conferir: ela já tinha mandado
    tirá-la, a GTK obedeceu em 25/08 (`lightbar_actions._PREFIXO_DESENHO`
    passou a dizer *"Desenho que mandamos"*) e o mockup a reintroduziu.

    A FRASE DO DESENHO DAS 5 LUZES SAIU JUNTO — 02/09/2026, e é o mesmo defeito
    uma camada adiante. Ela dizia *"Desenho que mandamos: desenho do PN —
    automático, do número deste controle"*, e isso é uma afirmação sobre o MERGE
    do backend (`core/backend_pydualsense._merged_desired_for_key`)::

        default global do perfil  <  camada AUTOMÁTICA  <  override por-uniq
                                                        <  co-op  <  jogo

    **Este pacote não vê o override por-uniq.** O `state_full` publica, por
    controle, exatamente as chaves de
    `daemon/ipc_handlers._enrich_controllers_per_controller` — `lightbar_rgb`,
    `lightbar_on`, `lightbar_source`, `player_slot`, `inputs`… — e nenhum campo
    do desejado; `interface/aba02.py:1403` já dizia isso com todas as letras
    (*"publica o ``player_slot`` e NÃO publica ``player_leds``"*). E o override
    é justamente onde a janela GTK escreve quando ela aplica um desenho:
    `lightbar_actions._enviar_player_leds` manda `player_leds_set_detalhado(…,
    uniq=…)` → `ipc_handlers._apply_por_uniq` → `apply_output_for`, *"que
    registra o override por-uniq"*.

    REPRODUZIDO em 02/09/2026, com o merge REAL do backend e nenhum aparelho
    (o dublê é o de `test_troca_de_player_01_a_escolha_sobrepoe.py`)::

        override por-uniq   o produto MANDA          a tela DIZIA
        nenhum              [F,T,F,T,F] (o do P2)    desenho do P2 — automático
        [T,F,F,F,T]         [T,F,F,F,T]              desenho do P2 — automático

    A segunda linha é a tela afirmando o contrário do que sai no fio. Vale a
    regra dela: *"se não tá mostrando agora, não tem info pra mostrar no
    produto"* — campo sem informação **não mostra nada**.

    O QUE SOBRA É O QUE SE MEDE, e a frase continua tendo dono no motor: a
    da BARRA é o primeiro retorno de `controller_card.rotulo_lightbar` — a
    mesma que os cards da GTK usam, e que sabe os quatro estados em que a cor
    publicada **não** é a que está no plástico. `""` quando não há ressalva.

    A FRASE DO CO-OP SAIU — O-CO-OP-LOCAL-SAI-01, 25/09/2026, pedido dela
    (`D-2409-O-CO-OP-LOCAL-SAI`). Com mais de um jogador a dica somava
    *"Desenho que mandamos: o do co-op — com o co-op ligado, é ele que manda
    nas 5 luzes"* (o ramo 1 de `lightbar_actions.texto_do_desenho_aceso`), e a
    frase tratava o co-op como um modo que se liga: o Hefesto dá um controle
    virtual a cada jogador sempre, e quem numera as cinco lâmpadas é ele
    (`D-2309-O-HEFESTO-MANDA-NO-NUMERO`). O que a frase explicava — que
    escolher um desenho à mão não adianta — perdeu o assunto em 07/09, quando
    a botoeira saiu e as lâmpadas passaram a espelhar a linha `Jogador` logo
    acima. **A dica agora é a mesma com um jogador ou com quatro**, e a régua
    é `tests/unit/test_o_co_op_local_saiu.py`.

    :param nome: o modelo VIVO, o que a mesa sabe — nunca o do desenho.
    :param via: `USB`/`BT` de agora. `—` ou vazio some da frase em vez de
        virar `(—)`: um travessão entre parênteses não diz nada a ninguém.
    :param recado: o primeiro retorno de `rotulo_lightbar`, ou `""`.
    """
    frases = [recado] if recado else []
    quem = f"{nome} ({via})" if via and via != "—" else nome
    return (f"{quem} · " + " · ".join(frases)) if frases else quem


def _da_mesa(ctx: Contexto, uniq: str) -> dict[str, Any]:
    """O item da MESA daquele controle, ou `{}`."""
    for m in ctx.mesa:
        if str(m.get("uniq") or "") == uniq:
            return m
    return {}


def _numero(ctx: Contexto, c: dict[str, Any]) -> int:
    """O número deste controle, pela regra do MOTOR — e ela tem UM dono.

    `app/actions/base.numero_do_controle` é a fonte única (COR-01/D6): o
    `player_slot` de sessão, que sobrevive a desconectar e reconectar, com queda
    para a posição. O docstring dele conta por que existe: *"Existia uma cópia
    dessa regra em cada tela (…) Duas verdades na mesma janela sobre qual é o
    'Controle 1'."*

    ESTA ABA TINHA A TERCEIRA CÓPIA, e ela era a errada: o rótulo lia só
    `player`, que é `None` para quem não é jogador do co-op — e a mesma aba
    escrevia `Modelo: P—` no rótulo com o botão `2` ACESO logo abaixo (D2,
    fotografado em 02/09/2026). A quarta cópia estava no gesto `auto`
    (`player_slot or player or 1`).

    A MESA JÁ CHAMA O MOTOR: `mesa_viva.mesa_do_estado:324` põe
    `numero_do_controle(entrada)` em `jogador`. Ler dela é o caminho mais curto
    e é o que faz esta aba concordar com a fita e o cabeçalho acima dela;
    perguntar direto ao motor é a queda para quando o controle não está na mesa.
    """
    da_mesa = _da_mesa(ctx, str(c.get("uniq") or "")).get("jogador")
    if isinstance(da_mesa, int) and not isinstance(da_mesa, bool):
        return da_mesa
    from hefesto_dualsense4unix.app.actions.base import numero_do_controle

    return numero_do_controle(c)


def _cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, ou `""` quando ninguém sabe ainda."""
    if not slug:
        return ""
    try:
        import monta

        # dela não têm hexa amostrado e devolvem `url(#hachura-sem-hex)`, que
        return str(monta.cor_de_css(slug))
    except Exception:
        return ""


def um_botao_de_player(nome: str, meu: int, n: int,
                       dono: dict[str, Any] | None, *, quantos: int) -> str:
    """Um número, na coluna de UM controle: dá-lo a este troca-o com o dono.

    ESTA FUNÇÃO TEM DOIS CHAMADORES E UM DONO. O gerador `aba04.py` a chama para
    desenhar a bancada; o pacote a chama a cada tique para pintar a fileira
    viva. Enquanto eram duas escritas, o botão do desenho e o botão do produto
    podiam divergir sem ninguém ver — e é o mesmo defeito que deixou a
    `novo-layout/` divergir 25 KB calada.

    O DONO SÓ EXISTE SE ELE ESTIVER NA MESA — 31/08/2026. O `title` dizia *"o
    Galactic Purple, que tem o 3 hoje"* com o Galactic Purple DESCONECTADO. Ele
    não tem o 3 hoje; ele não tem nada hoje.

    SÃO QUATRO ESTADOS, E A TELA MOSTRAVA DOIS — ver `ANEL_INCERTO`:

        livre          ninguém tem este número      sem anel
        tomado         e eu sei a cor do dono       anel cheio, na cor do plástico
        tomado, sem cor  o dono está aqui, a cor não chegou  anel TRACEJADO
        fora da mesa   não há controles bastante    apagado, e a dica diz o número

    O terceiro caía no primeiro, e a diferença viajava só no `title`.

    O QUARTO NASCEU DE UM CLIQUE — 03/09/2026, medido no produto instalado com
    UM controle no cabo. A dica dizia **"Player 3 — livre."**, o botão era
    idêntico ao 1 (`disabled:false`, `cursor:pointer`, mesma borda), e clicar
    devolvia `RuntimeError: Esse número é maior do que a quantidade de controles
    ligados`. *Livre* quer dizer disponível; o número não estava disponível. A
    tela AFIRMAVA o contrário do que o produto faria — e com `quantos=1` isso
    valia para TRÊS dos quatro botões da fileira.

    `quantos` É A MESA, NÃO OS DONOS, e a distinção é o que faz a conta bater
    com a do daemon: quem recusa compara o número com **quantos controles estão
    ligados**, e `donos` só tem os que têm item de mesa. Contar `donos` diria
    "fora da mesa" a um número que o produto aceitaria.

    É KEYWORD-ONLY e SEM PADRÃO de propósito: um padrão faria o chamador que
    esquecesse voltar calado ao estado que este parágrafo descreve.
    """
    cor = _cor_do_plastico(str(dono.get("cor") or "")) if dono else ""
    #: O ENDEREÇO E O ALVO ANDAM JUNTOS — endereço sem alvo é meia fechadura, e
    onde = (f'data-hef="{endereco_do_anel(n)}" '
            f'data-hef-alvo="{ALVO_DO_PLASTICO}"')
    if dono is None:
        anel = ""
    elif cor:
        anel = f'<i class="dono" {onde} style="--plastico:{cor}"></i>'
    else:
        anel = f'<i class="dono incerta" {onde} style="{ANEL_INCERTO}"></i>'
    fora = dono is None and n > quantos
    if n == meu:
        dica = f"O {nome} é o Player {n} hoje."
    elif fora:
        dica = f"Player {n}"
    elif dono is None:
        dica = f"Player {n} — livre."
    else:
        dica = (f"Dar o {n} ao {nome}: o {dono['nome']} fica com o {meu}. "
                f"Os dois trocam.")
    marca = " ".join(x for x in ("on" if n == meu else "", "fora" if fora else "") if x)
    aria = ' aria-disabled="true"' if fora else ""
    return (f'<button class="{marca}"{aria} '
            f'data-gesto="player" data-player="{n}" title="{dica}">{anel}{n}</button>')


def fileira_de_players(nome: str, meu: int, donos: dict[int, dict[str, Any]],
                       recuo: str = "", *, quantos: int) -> str:
    """Os quatro botões de uma coluna, em HTML — o miolo de `.players`.

    POR QUE A FILEIRA INTEIRA, e não um endereço por botão: o que muda com o
    dado é **qual botão fica `on`** e **o texto da dica**, e a pintura desta
    casa (`hefesto_vivo.escrever`) sabe escrever texto, largura, fundo, valor e
    HTML — **classe, não**. Com um `data-campo` por botão, os quatro só podiam
    receber texto, e texto num `<button>` apaga o anel do dono que está dentro
    dele. A fileira inteira pelo alvo `html` é o mesmo degrau que a fita e o
    mapa do gabinete já usam: um bloco cujo conteúdo muda com a mesa se troca
    inteiro. O ouvinte de clique é delegado no documento, então trocar o HTML
    não desliga botão nenhum.

    `quantos` ATRAVESSA — ver `um_botao_de_player`, onde está a medição.
    """
    return "\n".join(recuo + um_botao_de_player(nome, meu, n, donos.get(n),
                                                quantos=quantos)
                     for n in NUMEROS)


ENDERECO_DO_BRILHO_DAS_LUZES = "brilho-luzes"
GESTO_DO_BRILHO_DAS_LUZES = "brilho-luzes"
ROTULO_DO_BRILHO_DAS_LUZES = {
    "fraco": "Fraco",
    "medio": "Médio",  # noqa-acento: chave ASCII, o rótulo ao lado
    "forte": "Forte",
}


def fileira_de_brilhos_das_luzes(escolhido: str, recuo: str = "") -> str:
    """As três pílulas de UM controle, em HTML — o miolo da `.brilhos`."""
    from hefesto_dualsense4unix.core.led_control import BRILHOS_DAS_LUZES

    botoes = []
    for valor in BRILHOS_DAS_LUZES:
        rotulo = ROTULO_DO_BRILHO_DAS_LUZES[valor]
        marca = ' class="on"' if valor == escolhido else ""
        botoes.append(
            f'{recuo}<button{marca} data-gesto="{GESTO_DO_BRILHO_DAS_LUZES}" '
            f'data-luzes="{valor}" title="Luzes de número: {rotulo}">{rotulo}</button>')
    return "\n".join(botoes)


#: A LINHA DA LUZ DO JOGO — 04/10/2026, desenho aprovado em `docs/process/estudos/2026-10-04-o-jogo-
#: decide/` (item 3, «Uma linha curta embaixo das cores», sem botão novo). A regra já vale no
#: produto desde a 1.5: com o jogo pintando a barra, vale a cor do jogo; sem jogo, a do perfil.
#: A tela só a diz.
ENDERECO_DA_LUZ_DO_JOGO = "luz-do-jogo"

FRASE_DA_LUZ_DO_JOGO = "O jogo pinta por cima; sem jogo, a sua cor."


def frase_da_luz_do_jogo(pintando: list[int], conectados: int) -> str:
    """A linha curta embaixo das cores, em HTML (alvo `html`).

    ``pintando`` são os números de jogador dos controles em que o JOGO pinta a barra agora, lidos do
    ``luz_do_jogo`` do `state_full`. Todos pintando: «Agora: a cor do jogo»; só alguns, e a frase
    diz quais (a luz de um controle não é a luz dos outros). Ninguém pintando, só a regra. A luz
    nunca sai preta: a regra vale com ou sem jogo, e é por isso que a linha não tem botão.
    """
    if not pintando:
        return FRASE_DA_LUZ_DO_JOGO
    numeros = sorted(set(pintando))
    if len(numeros) >= max(1, conectados):
        agora = "Agora: a cor do jogo"
    else:
        nomes = [f"P{n}" for n in numeros]
        onde = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
        agora = f"Agora: a cor do jogo {'no' if len(nomes) == 1 else 'nos'} {onde}"
    return f"{FRASE_DA_LUZ_DO_JOGO} <b>{agora}</b>"


_TEM_A_LINHA_DA_LUZ: bool | None = None


def a_pagina_tem_a_linha_da_luz() -> bool:
    """A página PUBLICADA tem onde pôr a linha da luz do jogo? Antes do `--publicar`, não."""
    global _TEM_A_LINHA_DA_LUZ
    if _TEM_A_LINHA_DA_LUZ is None:
        from hefesto_dualsense4unix.interface import onde

        try:
            pagina = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
        except OSError:
            pagina = ""
        _TEM_A_LINHA_DA_LUZ = f'data-campo="{ENDERECO_DA_LUZ_DO_JOGO}"' in pagina
    return _TEM_A_LINHA_DA_LUZ


_TEM_AS_PILULAS: bool | None = None


def a_pagina_tem_as_pilulas() -> bool:
    """A página PUBLICADA tem onde pôr as três pílulas do brilho das luzes?"""
    global _TEM_AS_PILULAS
    if _TEM_AS_PILULAS is None:
        from hefesto_dualsense4unix.interface import onde

        try:
            pagina = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
        except OSError:
            pagina = ""
        _TEM_AS_PILULAS = f'data-campo="{ENDERECO_DO_BRILHO_DAS_LUZES}"' in pagina
    return _TEM_AS_PILULAS


def brilho_das_luzes_do_controle(p: dict[str, Any] | None, uniq: str) -> str:
    """A palavra do brilho das luzes de número DAQUELE controle, lida do perfil.

    A MESMA ORDEM DO `brilho_do_controle` logo acima, e pela mesma razão: o
    override por controle vence a seção global, e a seção global vence o
    padrão do esquema (`LedsConfig.player_led_brightness`, o Fraco). Aqui só se
    lê o disco; quem resolve as camadas no aparelho é o daemon.

    SEM PERFIL LIDO devolve o padrão, e não `""`: o esquema é o dono do
    padrão, e todo controle nasce no Fraco (a decisão dela).
    """
    from hefesto_dualsense4unix.core.led_control import (
        BRILHO_DAS_LUZES_PADRAO,
        BRILHOS_DAS_LUZES,
    )

    if not isinstance(p, dict):
        return BRILHO_DAS_LUZES_PADRAO
    leds = p.get("leds")
    global_ = leds.get("player_led_brightness") if isinstance(leds, dict) else None
    alvo = chave_do_override(uniq)
    meu = next((v for k, v in (p.get("controllers") or {}).items()
                if chave_do_override(str(k)) == alvo), None)
    seus = (meu.get("leds") or {}) if isinstance(meu, dict) else {}
    valor = seus.get("player_led_brightness", global_) if isinstance(seus, dict) else global_
    return valor if valor in BRILHOS_DAS_LUZES else BRILHO_DAS_LUZES_PADRAO


def brilho_das_luzes_acesas(c: dict[str, Any] | None, p: dict[str, Any] | None,
                            uniq: str) -> str:
    """A palavra do brilho que as luzes de número DESTE controle acendem agora."""
    from hefesto_dualsense4unix.core.led_control import BRILHOS_DAS_LUZES

    vivo = (c or {}).get("brilho_das_luzes")
    if isinstance(vivo, str) and vivo in BRILHOS_DAS_LUZES:
        return vivo
    return brilho_das_luzes_do_controle(p, uniq)


def desenho_da_luz(tinta: str, brilho: float, jogador: int, dica: str = "",
                   recuo: str = "", estado: str = "") -> str:
    """O miolo do `.aceso`: as duas tiras e as cinco lâmpadas, VIVAS.

    O DEFEITO QUE ESTA FUNÇÃO MATA está fotografado na tela dela em
    02/09/2026, com dois controles na mesa::

        a célula LEDs das colunas P1 e P2 mostrando a palavra `Aceso`

    O `.aceso` é um DESENHO — duas tiras de luz e as cinco lâmpadas do
    indicador —, e o pacote escrevia nele a palavra `Aceso` por um `data-campo`
    de alvo `texto`. `escrever()` faz `el.textContent = t`, que **apaga os
    filhos**: as duas tiras e as cinco lâmpadas sumiam no primeiro tique, e a
    régua do mockup contava isso como PRODUTO, porque o valor MUDOU. É a mesma
    família do `balanceado` escrito dentro dos quatro botões da Vibração e da
    contagem escrita dentro do `<tbody>` da Perfis.

    A PERGUNTA QUE SEPARA OS DOIS CASOS, e vale para toda aba: *isto é um DADO
    ou é o DESENHO?* Um desenho cujo conteúdo muda com o dado se troca INTEIRO,
    pelo alvo `html` — o mesmo degrau que a fita, o mapa do gabinete e a fileira
    de players já usam.

    UM DONO, DOIS CHAMADORES: o gerador `aba04.py` desenha a bancada com esta
    função e o pacote pinta o produto com ela a cada tique. Enquanto eram duas
    escritas, o desenho e o produto podiam divergir sem ninguém ver.

    NADA AQUI É NOVO — tudo tem dono no motor:

    * as cinco lâmpadas saem de `monta.luzinhas`, que lê
      `core/led_control.player_led_pattern` (o MESMO padrão que o daemon acende);
    * a tinta é `_tinta`, isto é `monta.tom_da_casa` do hex vivo;
    * quem decide se HÁ cor a afirmar é `controller_card.rotulo_lightbar` — o
      chamador passa `""` quando não há;
    * a `dica` inteira é `dica_da_luz` — o nome VIVO mais as frases do motor
      que este pacote pode conferir, e nada além delas (ver lá).

    A DICA VIAJA NAS TRÊS PEÇAS, e não na célula em volta. O `title` da célula
    é um ATRIBUTO, e o piloto não tem alvo de pintura para atributo — os alvos
    são `texto`, `largura`, `fundo`, `valor`, `html`, `classe` e `cor`
    (`hefesto_vivo.escrever`). Um `title` na célula, portanto, fica CONGELADO no
    que o gerador escreveu: era ele que dizia *"O Cosmic Red aceso…"* na coluna
    de um controle branco. Posto nas peças, ele entra pelo mesmo alvo `html` que
    troca o desenho, e muda com a mesa. **RELATO:** um alvo `titulo` no piloto
    resolveria isto para as dezenove dicas congeladas desta aba de uma vez.

    :param tinta: o hex JÁ no tom da casa. `""` desenha a tira APAGADA
        (`TIRA_APAGADA`), e nunca uma tira sem estilo — ver a constante. Com
        `estado=INCERTA` a tinta não é olhada: quem não sabe não pinta.
    :param brilho: de 0.0 a 1.0, a opacidade das duas tiras ACESAS. A apagada
        não tem brilho: uma barra desligada a 30% seria 30% de nada.
    :param jogador: o número deste controle — e ele é a ÚNICA fonte das cinco
        lâmpadas desde 07/09/2026. Elas espelham a linha `Jogador`; não há
        segundo caminho que as acenda, e por isso não há como a célula `LEDs`
        divergir do número que a célula de cima mostra.
    :param dica: a frase de `dica_da_luz`, ou `""`. Sem ela as peças saem sem
        `title`, que é o que o desenho fazia antes de haver frase viva.
    :param estado: `ACESA`, `APAGADA` ou `INCERTA` — o que `estado_da_tira`
        respondeu. `""` quer dizer **sem estado declarado**, e aí a tinta
        decide: é o que a BANCADA sabe, porque o gerador não tem motor a
        perguntar. Nunca vale `INCERTA` por omissão — inventar "não sei" onde
        ninguém perguntou seria a tela afirmando uma dúvida que não existe.
    """
    import monta

    incerta = estado == INCERTA
    estilo = (TIRA_APAGADA if (incerta or estado == APAGADA or not tinta)
              else f"background:{tinta};color:{tinta};opacity:{brilho}")
    veste = f' style="{estilo}"'
    marca = (f' data-campo="{ENDERECO_DA_INCERTA}" data-hef-alvo="classe"'
             f' data-hef-classe="{CLASSE_DA_INCERTA}"')
    aviso = f" {CLASSE_DA_INCERTA}" if incerta else ""
    diz = f' title="{dica}"' if dica else ""
    tira = f'<span class="tira-luz %s{aviso}"{veste}{marca}{diz}></span>'
    #: aba com os quatro DualSense na mesa: *"pq tá surgindo os leds no lado da
    #: a forma final, que é o contrato desta função: *"só olhar a linha de cima
    #: reenvio (`reenviar-desenho`). Ficaram as DUAS tiras — *"os leds. barra de
    #: ESPELHO do número, sem escolha própria.
    try:
        lampadas = monta.luzinhas(jogador)
    except KeyError:
        # O DONO SABE O OVERFLOW E O ATALHO DA BANCADA NÃO. `player_led_pattern`
        # DualSense pode legitimamente cair no slot 5+"* e que *"≥9 cai no padrão
        # `monta.luzinhas(9)` levanta `KeyError`. Medido em 02/09/2026.
        lampadas = ""
    return "\n".join(recuo + linha for linha in (
        tira % "esq",
        f'<span class="pad"{diz}>{lampadas}</span>',
        tira % "dir",
    ))


#: filho que ainda não existe.
SECAO_DA_TROCA = ".nota-troca"

TITULO_DA_TROCA = "Trocar o número: o antes e o depois"

CAIXA_DA_COLUNA = ".ctrl"


def _folha_do_plastico(mesa: list[dict[str, Any]], caixa: str) -> str:
    """A folha viva do casco, com o dono que a aba Navegação já tem.

    IMPORTA TARDE de propósito, como o `import monta` das outras funções deste
    módulo: os pacotes das dez abas se registram no import, e uma dependência no
    topo entre dois deles amarraria a ordem de carga a um detalhe de quem
    escreveu primeiro.

    UM DONO, DOIS CHAMADORES — a mesma disciplina da `fileira_de_players` e do
    `desenho_da_luz`. Copiar a função para cá daria duas leituras do
    `ds_limpo.svg` que divergem no primeiro modelo novo.
    """
    from . import a06_navegacao

    return a06_navegacao.folha_do_plastico(mesa, caixa)


ALVO_DA_BARRA = '[id$="-lightbar"]'
ALVO_DAS_LAMPADAS = '[id*="-led-jogador-"]'

BARRA_APAGADA = "initial"

LUZ_APAGADA = "#3f4350"

ESCOPO_DO_DESENHO = ".luz-grade"


def token_das_luzinhas(nome: str) -> str:
    """O valor de um token do `CSS_LUZINHAS` — PERGUNTADO a ele, nunca digitado."""
    import re

    import monta

    achado = re.search(rf"{re.escape(nome)}\s*:\s*([^;}}]+)", monta.CSS_LUZINHAS)
    if achado is None:
        raise SystemExit(
            f"ERRO em 04-iluminacao: `{nome}` sumiu do `monta.CSS_LUZINHAS` — o "
            f"desenho grande lê de lá o par de cores das lâmpadas.")
    return achado.group(1).strip()


def tokens_da_luz() -> str:
    """As duas cores das lâmpadas, declaradas onde o DESENHO as alcança.

    UM DONO, DOIS CHAMADORES — a mesma disciplina da `fileira_de_players`. O
    gerador as põe na folha da página, que é o que a bancada precisa para se ver
    sozinha, sem daemon; este pacote as põe na folha VIVA, porque a página
    PUBLICADA ainda não as tem — e o publicado é o que está na tela dela hoje.
    Duas escritas do mesmo par dariam dois brancos na mesma célula.

    O `--luz-apagada` NÃO ENTRA, e a mordida é que decidiu: ver `LUZ_APAGADA`.
    """
    return (f"{ESCOPO_DO_DESENHO}{{"
            f"--led-apagado:{token_das_luzinhas('--led-apagado')};"
            f"--led-aceso:{token_das_luzinhas('--led-aceso')}}}")


def folha_da_luz(luzes: dict[str, tuple[str, int | None]],
                 caixa: str = CAIXA_DA_COLUNA) -> str:
    """A folha viva da LUZ: a barra e as cinco lâmpadas do DESENHO GRANDE.

    POR QUE ELA PRECISOU EXISTIR, e a medição está no DOM vivo de 03/09/2026, na
    mesa dela, com UM controle no cabo (``ensaios/a_luz_do_desenho_e_a_luz_do_aparelho.py``)::

        p1   o aparelho diz (0, 0, 255)   e o desenho acende (126, 184, 212)
        p1   o número 1 pede a lâmpada 3  e o desenho não acende nenhuma

    O `#7EB8D4` é o `--luz` que o GERADOR crava no `<g>` — a cor do MOCKUP,
    parada na tela dela debaixo de um hexadecimal que já dizia `#0000FF`. A
    mesma célula afirmando duas cores, e quem olha lê o desenho antes do número.

    POR QUE UMA FOLHA, e não um campo — a mesma razão de `folha_do_plastico`: o
    pintor sabe escrever texto, largura, fundo, valor, `innerHTML`, classe, cor,
    atributo e `--plastico`, e **nenhum deles escreve um `--luz`**. Reescrever o
    SVG inteiro pelo `innerHTML` custaria as 370 linhas do desenho a cada meio
    segundo e nunca sossegaria (o navegador normaliza marcação). O `innerHTML` de
    um `<style>` é TEXTO, e texto volta como foi escrito.

    O `!important` NÃO É FORÇA BRUTA, e é o único caminho: o `--luz` do mockup
    mora no atributo `style` do `<g>`, e declaração de linha vence folha. A marca
    `led-on` das lâmpadas tem o mesmo problema — ela é cravada pelo gerador nos
    `<rect>` que o MOCKUP escolheu, e some do cálculo assim que uma regra
    `!important` de igual especificidade pinta as cinco.

    A ORDEM DAS DUAS REGRAS DE LÂMPADA É O QUE DECIDE: as cinco apagam primeiro,
    as do padrão acendem depois. As duas valem (0,3,0) e as duas são
    `!important`, então quem vem por último ganha — escrever na ordem inversa
    apagaria a lâmpada que acabou de acender.

    SEM COR A AFIRMAR, A BARRA APAGA. É a regra dela — *"se não tá mostrando
    agora, não tem info pra mostrar no produto"* — e ela vale para os quatro
    lugares: um lugar sem controle recebe as regras de apagado do mesmo jeito,
    senão o `--luz` do mockup fica aceso num lugar que diz "Desconectado".

    :param luzes: por lugar (`p1`…`p4`), o par `(hexadecimal da barra, número)`.
        O hexadecimal vazio ou `—` apaga a barra; o número `None` apaga as cinco
        lâmpadas. Um lugar ausente do dicionário é tratado como apagado.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    from . import TODOS_OS_LUGARES, TRAVESSAO

    regras: list[str] = [tokens_da_luz()]
    for pref in sorted(TODOS_OS_LUGARES | set(luzes)):
        onde = f'{caixa}[data-controle="{pref}"]'
        cor, numero = luzes.get(pref) or ("", None)
        cor = "" if str(cor).strip() in ("", TRAVESSAO) else str(cor).strip()
        regras.append(f"{onde} {ALVO_DA_BARRA}"
                      f"{{--luz:{cor or BARRA_APAGADA} !important}}")
        regras.append(f"{onde} {ALVO_DAS_LAMPADAS}"
                      f"{{fill:var(--led-apagado) !important;"
                      f"filter:none !important}}")
        if not isinstance(numero, int) or isinstance(numero, bool):
            continue
        for i, acesa in enumerate(player_led_pattern(numero), 1):
            if acesa:
                regras.append(
                    f'{onde} [id$="-led-jogador-{i}"]'
                    f"{{fill:var(--led-aceso) !important;"
                    f"filter:drop-shadow(0 0 .5px var(--led-aceso)) !important}}")
    return "".join(regras)


def _luzinhas(numero: int) -> str:
    """As cinco lâmpadas daquele número, ou `""` quando ninguém sabe o padrão.

    O guarda é o mesmo de `desenho_da_luz`, e pela mesma razão medida:
    `monta.PADRAO_JOGADOR` só precomputa 1..8 e `monta.luzinhas(9)` levanta
    `KeyError`, enquanto `core/led_control.player_led_pattern` responde a
    qualquer número. Enquanto só o gerador chamava, o número era 1..4.
    """
    import monta

    try:
        return str(monta.luzinhas(int(numero)))
    except (KeyError, TypeError, ValueError):
        return ""


def item_da_troca(nome: str, numero: int, plastico: str,
                  mexeu: bool = False) -> str:
    """Um controle com um número, no antes/depois do rodapé.

    `data-hef` PELA MESMA RAZÃO DO ANEL DA FILEIRA: o `--plastico` mora no
    `style` DESTE elemento, e a régua da identidade julga o `--plastico` no
    elemento que o carrega. Aqui ele não é congelado — a seção inteira é um
    `blocos:` que o produto reescreve com a mesa viva —, e o endereço é o que
    diz isso.

    E O ENDEREÇO GANHOU O ALVO EM 03/09/2026, porque só ele NÃO bastava. O
    `blocos:` reescreve o miolo por `document.querySelector`, e nem a régua da
    identidade nem a do mockup têm como saber disso lendo o HTML — a troca mora
    no JavaScript, não na marcação. Com `data-hef-alvo="plastico"` o pintor
    escreve a variável no PRÓPRIO item (`cores_da_troca` manda a lista, na
    ordem do documento), e o que era invisível às duas réguas passa a deixar o
    selo da visita.

    O ANEL TRACEJADO CHEGA AQUI TAMBÉM — 03/09/2026, e pela mesma razão do
    vizinho (`ANEL_INCERTO`). Todo item desta seção É um controle na mesa, então
    aqui não há "livre" a confundir; o que havia era o anel SUMINDO. Sem
    `--plastico`, a folha (`border:2px solid var(--plastico)`) fica inválida no
    tempo de computar, o `border-style` cai para `none` e a linha perde a marca
    de identidade que as vizinhas têm — sem nada dizer que a diferença é *"não
    sei a cor"*, e não *"este é de outro tipo"*.

    :param plastico: o hex da casca, ou `""` — e sem hex o item sai com o anel
        TRACEJADO, que é como esta aba diz "não sei" desde a decisão 9 dela.
    """
    veste = f' style="--plastico:{plastico}"' if plastico else ""
    anel = ('<i class="dono"></i>' if plastico
            else f'<i class="dono incerta" style="{ANEL_INCERTO}"></i>')
    return (f'<span class="troca-item{" mexeu" if mexeu else ""}"'
            f' data-hef="{ITEM_DA_TROCA}"'
            f' data-hef-alvo="{ALVO_DO_PLASTICO}"{veste}>'
            f'{anel}<span class="np">P{numero}</span>'
            f'<span>{nome}</span>{_luzinhas(numero)}</span>')


def _ordem_da_troca(mesa: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A ordem em que a seção da troca desenha os controles."""
    return sorted(mesa, key=lambda c: int(c.get("jogador") or 0))


def cores_da_troca(mesa: list[dict[str, Any]]) -> list[str]:
    """A cor do plástico de cada `.troca-item`, na ordem do documento.

    SÃO DUAS LINHAS COM OS MESMOS CONTROLES — o ANTES e o DEPOIS —, e o que
    muda entre elas é o número, nunca a casca: a troca dá um número a outro
    aparelho, não repinta plástico nenhum. Por isso a lista é a mesma sequência
    duas vezes.

    VAZIA QUANDO NÃO HÁ TROCA A CONTAR: com menos de dois controles a seção não
    desenha item nenhum (ver `secao_da_troca`), e uma lista com valor a mais
    escreveria num item que não existe.
    """
    ordenada = _ordem_da_troca(mesa)
    if len(ordenada) < 2:
        return []
    cores = [_cor_do_plastico(str(c.get("cor") or "")) for c in ordenada]
    return cores + cores


def secao_da_troca(mesa: list[dict[str, Any]], recuo: str = "  ") -> str:
    """A seção "Trocar o número" inteira, com a mesa que lhe derem.

    POR QUE ELA DEIXOU DE SER TEXTO FIXO — 03/09/2026, a lei dela: *"se no topo
    tá mostrando controle white player 1, então cada aba vai usar os controles
    lá de cima. Não mistura com a info dos mockups."* Esta seção é o exemplo do
    caso REAL dela, de 26/08 (*"o meu controle azul é o player 2 e antes de
    irmos pro jogo ele tem que ser o player 1"*) — e o exemplo estava escrito
    com os dois controles do DESENHO, num rodapé que o produto renderiza.

    UM DONO, DOIS CHAMADORES, como a fileira de players e o desenho da luz: o
    gerador desenha a bancada com esta função e o pacote a manda a cada tique
    por `blocos:`. Enquanto fossem duas escritas, as duas podiam divergir.

    A TROCA PRECISA DE DOIS. Com menos de dois controles na mesa não há exemplo
    a contar, e a seção diz isso em vez de inventar um segundo controle — é a
    regra dela: campo sem informação não mostra nada.
    """
    r = recuo
    ordenada = _ordem_da_troca(mesa)
    cabeca = f"{r}<h2>{TITULO_DA_TROCA}</h2>"
    if len(ordenada) < 2:
        quantos = "nenhum controle" if not ordenada else "um controle só"
        return (f"{cabeca}\n"
                f"{r}<p>A troca acontece entre <b>dois</b> controles, e há "
                f"{quantos} agora. Com dois ligados, esta seção mostra o antes e "
                f"o depois com eles.</p>")

    from hefesto_dualsense4unix.core.led_control import cor_automatica

    tem, quer = ordenada[0], ordenada[1]
    depois = {c["pref"]: int(c["jogador"] or 0) for c in ordenada}
    depois[quer["pref"]] = int(tem["jogador"] or 0)
    depois[tem["pref"]] = int(quer["jogador"] or 0)

    def _linha(rotulo: str, numero_de: Any, mexeu_de: Any) -> str:
        itens = "\n".join(
            f"{r}    " + item_da_troca(str(c.get("nome") or "—"), numero_de(c),
                                       _cor_do_plastico(str(c.get("cor") or "")),
                                       mexeu_de(c))
            for c in ordenada)
        return (f'{r}  <div class="troca-linha">'
                f'<span class="troca-rot">{rotulo}</span>\n{itens}\n{r}  </div>')

    numeros = " · ".join(str(int(c["jogador"] or 0)) for c in ordenada)
    return "\n".join([
        cabeca,
        f'{r}<p>O caso é o seu, de 26/08 — <i>"o meu controle azul é o player 2 e '
        f"antes de irmos pro\n{r}jogo ele tem que ser o player 1\"</i>. Na coluna "
        f'do <b>{quer["nome"]}</b>, clique no\n{r}<b>{tem["jogador"]}</b>:</p>',
        "",
        f'{r}<div class="troca">',
        _linha("Antes", lambda c: int(c["jogador"] or 0), lambda c: c is quer),
        f'{r}  <div class="troca-gesto">↓ clique no <b>{tem["jogador"]}</b> na '
        f'coluna do\n{r}    <b>{quer["nome"]}</b></div>',
        _linha("Depois", lambda c: depois[c["pref"]],
               lambda c: depois[c["pref"]] != int(c["jogador"] or 0)),
        f"{r}</div>",
        "",
        f"{r}<ul>",
        f"{r}  <li><b>Os dois trocam, os outros não se mexem.</b> É uma permutação: "
        f"ninguém repete\n{r}      número e ninguém fica sem. Por isso a fileira "
        f'oferece\n{r}      <span class="marca">{numeros}</span> — os números que'
        f"\n{r}      existem agora. Um número livre não teria com quem trocar, e "
        f"dá-lo deixaria um\n{r}      controle sem número.</li>",
        f"{r}  <li><b>As luzinhas seguem o número</b>, no padrão do produto: 1 é a "
        f"do <b>meio</b>,\n{r}      2 são as duas de dentro, 3 são as pontas e o "
        f"meio, 4 são quatro sem a do meio\n{r}      "
        f"(<code>core/led_control.py::player_led_pattern</code>).</li>",
        f"{r}  <li><b>E a cor da barra</b>, sem escolha à mão, é a do "
        f"<i>plástico</i>, e a do\n{r}      <i>número</i> só sem ela: depois "
        f'da troca o {quer["nome"]} acende\n{r}      <span class="marca">'
        f'{_hex(cor_automatica(int(tem["jogador"] or 0), _tom_do_plastico(quer)))}'
        f'</span> e o {tem["nome"]} acende\n{r}      <span class="marca">'
        f'{_hex(cor_automatica(int(quer["jogador"] or 0), _tom_do_plastico(tem)))}'
        f"</span>\n{r}      (<code>core/led_control.py::cor_automatica</code>).</li>",
        f"{r}</ul>",
    ])


def o_lugar_vazio() -> dict[str, str]:
    """O que a coluna SEM controle mostra nos dois desenhos da aba.

    PEDIDO DELA, 21/09/2026, com zero controles na mesa: *"os leds na linha
    dos leds do p3,p4 tem que aparecerem mas não aparecerem ligados como o p1 e
    o p2"*. O P1 e o P2 mostravam as duas tiras ACESAS no azul e no vermelho do
    mockup — o alvo `html` fica fora do travessão, e ninguém repintava —, e o
    P3 e o P4 um travessão seco no lugar do desenho.

    A LINHA LEDs É O DESENHO APAGADO: as duas tiras em `TIRA_APAGADA` e as
    cinco lâmpadas sem nenhuma acesa (`monta.luzinhas(0)`). Um lugar vazio não
    tem número de jogador, e acender o padrão do P1 diria um.

    A LINHA JOGADOR É O TRAVESSÃO: o P1 e o P2 a deixavam EM BRANCO (a folha
    esconde os botões de um lugar esvaziado) e o P3 e o P4 escreviam `—`. Uma
    fileira de botões não tem desenho apagado — não há número a escolher —, e
    o travessão é a palavra que o próprio desenho usa ali.

    O ESTILO VAI NO TRAVESSÃO, e é a regra da folha copiada: a tinta cinza e o
    centro do `.nada` moram em `.ctrl.vazia[data-conectado="nao"] .nada`, e o
    lugar que ESVAZIOU não é `.vazia` — medido na foto de 21/09, o traço do P1
    saía branco e encostado à esquerda ao lado do cinza centrado do P3. Uma
    regra nova na folha seria pixel da página publicada; esta é a mesma, no
    elemento.
    """
    pilulas = ({ENDERECO_DO_BRILHO_DAS_LUZES: ""} if a_pagina_tem_as_pilulas() else {})
    return {
        "luz": desenho_da_luz("", 1.0, 0, estado=APAGADA),
        "players": (f'<span class="nada" style="{ESTILO_DO_TRACO_VAZIO}">'
                    f'{TRAVESSAO}</span>'),
        **pilulas,
    }


#: A REGRA `.ctrl.vazia[data-conectado="nao"] .nada` da folha, letra por letra —
ESTILO_DO_TRACO_VAZIO = ("display:flex;align-items:center;justify-content:center;"
                         "height:100%;width:100%;color:var(--linha)")


@registrar("04-iluminacao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    p = perfil.ativo_que_vale(ctx.state.get("active_profile"))

    # `interface/cartao_do_controle.rotulo_lightbar` é a mesma que os cards da
    # (`recado, _base = …`) e decidia de novo, com `c.get("lightbar_on", True)`
    from hefesto_dualsense4unix.interface.cartao_do_controle import (
        cor_do_swatch,
        rotulo_lightbar,
    )

    donos: dict[int, dict[str, Any]] = {}
    for c in ctx.conectados:
        casa_dele = _da_mesa(ctx, str(c.get("uniq") or ""))
        if casa_dele:
            donos[_numero(ctx, c)] = casa_dele

    pecas = _as_pecas_da_mesa(ctx, p)
    cor_de = [peca["cor"] for peca in pecas]
    casas = as_casas_da_mesa(pecas)

    colunas: dict[str, dict[str, Any]] = {}
    #: A LUZ DO DESENHO GRANDE, por LUGAR — ver `folha_da_luz`. Ela nasce vazia
    #: e só recebe quem tem controle: `folha_da_luz` APAGA todo lugar que não
    luz_do_desenho: dict[str, tuple[str, int | None]] = {}
    jogo_pintando: list[int] = []
    for c, cor_dele in zip(ctx.conectados, cor_de, strict=True):
        uniq = str(c.get("uniq") or "")
        crua = cor_do_swatch(c)
        b = brilho_aceso(c, p, uniq)
        pct = None if b is None else round(float(b) * 100)
        casa = _da_mesa(ctx, uniq)
        n = _numero(ctx, c)
        nome = str(casa.get("nome") or "—")
        via = str(casa.get("via") or (c.get("transport") or "").upper() or "—")
        if c.get("luz_do_jogo") is True:
            jogo_pintando.append(n)
        recado, base = rotulo_lightbar(c, ctx.state)
        #: `rotulo_lightbar` devolve `(ressalva, COR BASE DO ACCENT)`, e a base
        #: Ali a base volta preenchida **com `lightbar_on` falso**, porque a
        #: QUEM RESPONDE A PERGUNTA DA TIRA É O PRIMEIRO RETORNO: `rotulo_lightbar`
        acesa = base if recado is None else None
        #: E ELA É A DO DONO DA MARCA — `_a_cor_de_agora`, a mesma do X nas
        pedida = cor_dele if crua else None
        estado = estado_da_tira(recado)
        #: folha de estilo (`folha_da_luz`), e um seletor CSS endereça o `p1`,
        if casa.get("pref"):
            luz_do_desenho[str(casa["pref"])] = (_hex(acesa) if acesa else "", n)
        colunas[uniq] = {
            "brilho": "—" if pct is None else f"{pct}%",
            #: trazer `data-hef-alvo="largura"` — as abas 02 e 05 têm, esta não
            "brilho-pct": pct,
            #: `on` por `data-hef-quando="#0000FF"` — os oito CHEIOS. Com o
            "hex": _hex(pedida),
            "tons": fileira_de_tons(uniq, casas, "              "),
            #: (`D-A-BORDA-E-A-IDENTIDADE-DA-PECA`).
            #: nenhum deles escreve um `--plastico`. A folha desta aba passou a
            "plastico": _cor_do_plastico(str(casa.get("cor") or "")),
            #: DualSense Cosmic Red desenhado a três centímetros dele.
            **({CAMPO_DO_DESENHO: colorway_do_aparelho(casa)}
               if a_pintura_alcanca_o_desenho() else {}),
            #: HTML publicado ainda diz `data-campo="aceso"`, e publicar é ato
            #: antes de 02/09 (`c.get("lightbar_on", True)`) era uma segunda
            "luz": desenho_da_luz(_tinta(cor_escolhida(acesa, b)),
                                  1.0 if b is None else float(b), n,
                                  dica_da_luz(nome, via, recado or ""),
                                  estado=estado),
            ENDERECO_DA_INCERTA: "sim" if estado == INCERTA else "",
            "identidade": f"P{n} • {nome} • {via}",
            #: recusar — ver `um_botao_de_player`. Não é `len(donos)`: quem não
            "players": fileira_de_players(nome, n, donos,
                                          quantos=len(ctx.conectados)),
            #: não diz (`brilho_das_luzes_acesas`, A-04-PERGUNTA-AO-DAEMON-VIVO-01):
            **({ENDERECO_DO_BRILHO_DAS_LUZES: fileira_de_brilhos_das_luzes(
                brilho_das_luzes_acesas(c, p, uniq), "              ")}
               if a_pagina_tem_as_pilulas() else {}),
            **{endereco_do_anel(k):
               _cor_do_plastico(str((donos.get(k) or {}).get("cor") or ""))
               for k in NUMEROS},
        }
    return {
        "colunas": colunas,
        LUGAR_VAZIO: o_lugar_vazio(),
        #: JavaScript, e o que se lê no HTML é um `--plastico` com endereço sem
        ITEM_DA_TROCA: cores_da_troca(ctx.mesa),
        ENDERECO_DO_AUTOMATICO: "sim" if automatico_do_perfil(p) else "",
        **({ENDERECO_DA_LUZ_DO_JOGO: frase_da_luz_do_jogo(jogo_pintando, len(ctx.conectados))}
           if a_pagina_tem_a_linha_da_luz() else {}),
        #: `perfil` saiu em 13/09/2026: o chip é das dez, dono `pacotes.topo()`.
        "sem_dono": {},
        "blocos": {SECAO_DA_TROCA: secao_da_troca(ctx.mesa),
                   "#plastico-vivo": (_folha_do_plastico(ctx.mesa, CAIXA_DA_COLUNA)
                                      + folha_da_luz(luz_do_desenho))},
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }


from . import gesto  # noqa: E402


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa."""
    return str(o.get("uniq") or "")


def sem_resposta_do_daemon() -> str:
    """A frase de "o Hefesto não respondeu" — e ela é do MOTOR, não daqui.

    OS TRÊS BOTÕES QUE ESCREVEM NO APARELHO SAÍAM CALADOS até 02/09/2026:
    `cor`, `apagar` e `auto` chamavam `p.led_set(...)` e `p.chamar(...)` e
    **jogavam fora o booleano**. `ipc_bridge._safe_call` devolve `(False, None)`
    para daemon offline, socket ausente, timeout de conexão e erro JSON-RPC —
    e nesses casos o clique dela sumia: a barra não mudava, a tela não dizia
    nada, e o segundo clique parecia o primeiro. É o defeito que o BRIEFING
    desta casa nomeia como o mais caro, e o quarto gesto desta MESMA aba
    (`player`) já o evitava lendo `(ok, motivo)`.

    A FRASE NÃO SE ESCREVE AQUI. `lightbar_actions._AVISO_HEFESTO_DESLIGADO` é
    a que a janela GTK mostra neste mesmo evento — o ramo em que o `led.set`
    por `uniq` volta sem corpo (`lightbar_actions.py`). Duas telas do
    mesmo produto dizendo coisas diferentes sobre o mesmo daemon desligado é a
    segunda verdade que esta casa persegue.

    ELA É PRIVADA POR CONVENÇÃO DE NOME, e não por contrato — do mesmo jeito
    que o próprio `lightbar_actions` lê `footer_actions._lista_de_secoes` e
    `._mensagem_de_aplicacao`. **RELATADO:** ela merece nome público, e isso é
    `app/actions/lightbar_actions.py`, fora do território deste arquivo.

    E ELA JÁ VEM HEDGED, o que é o ponto: *"o Hefesto **pode** estar
    desligado"*. O `bool` do bridge colapsa quatro causas numa só (offline,
    socket, timeout e erro do servidor), então afirmar a causa seria inventar
    um diagnóstico — a frase aponta a mais provável e diz onde olhar.
    """
    from hefesto_dualsense4unix.app.actions import lightbar_actions

    return str(lightbar_actions._AVISO_HEFESTO_DESLIGADO)


def _so_abriu_o_seletor(o: dict[str, Any]) -> bool:
    """O clique é a ABERTURA de um `<input>`, e não uma escolha dela.

    Os dois campos são do BOOTSTRAP e chegam em todo clique: `tipo` é o
    `tagName` do alvo e `evento` é o `ev.type`. Um `<input type="color">`
    dispara `click` ao abrir — com o valor VELHO — e `change` quando ela
    confirma; só o segundo é um pedido.

    SEM `evento` NO CLIQUE, NADA MUDA. As provas do contrato e a régua chamam o
    gesto com a carga mínima, e uma carga sem `evento` não é a abertura de nada
    — o guarda só fecha quando os DOIS campos dizem que foi abertura.

    E ELE VALE PARA O TRILHO PELO MESMO MOTIVO, com o tempo invertido —
    03/09/2026. Um `<input type="range">` clicado na pista dispara `input`,
    depois `change` e depois `click`; o BOOTSTRAP escuta `change` e `click`, e
    sem este guarda cada clique na pista viraria DUAS gravações no perfil dela e
    DUAS escritas no rádio. No seletor de cor o `click` chegava ANTES da escolha
    e carregava o valor velho; no trilho ele chega DEPOIS e carrega o mesmo
    valor. Nos dois casos ele não é um pedido — o pedido é o `change` —, e nos
    dois a resposta certa é sair calado: recusar dizendo poria uma frase de erro
    na tela dela por um gesto que ela fez uma vez só.

    O CHAMADOR QUE O PARIU SAIU EM 11/09/2026, e ele FICA. O seletor de cores
    do sistema deixou a guia (:data:`FORA_DA_GUIA`), e com ele o único caso em
    que o `click` chegava ANTES. Quem continua chamando são o `brilho` e o
    `auto-cores` — os dois pelo tempo invertido, que é o caso do trilho. A
    medição do caso de cor fica escrita porque é a razão de o guarda existir:
    apagá-la faria a próxima pessoa achar que ele é só para `range`.
    """
    return (str(o.get("tipo") or "").lower() == "input"
            and str(o.get("evento") or "").lower() == "click")


def _o_dono_da_frase() -> Any:
    """`LightbarActionsMixin`, importado TARDE — e a demora é obrigatória."""
    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        LightbarActionsMixin,
    )

    return LightbarActionsMixin


class _Janela:
    """O "host" mínimo que `app/textos_de_aplicacao.py` sabe interrogar.

    ELE NÃO É UMA JANELA E NÃO PRECISA SER. As três leituras que decidem a
    frase de um desfecho — `alvo_fora_da_mesa`, `modo_nativo_manda_no_output` e
    `mesa_vazia` — perguntam por `getattr` a um objeto qualquer; a GUI estável
    passa a si mesma porque é ela quem tem os campos, e a aba Status é quem os
    publica a cada tique do `state_full` (`status_actions.py`: o
    `_target_uniq_by_index` em `_update_target_maps`, o `_modo_nativo_ligado` em
    `_sync_modo_nativo_manda_no_output`, o `_coop_ligado` em
    `_sync_coop_governa_luzes`).

    Esta interface tem os MESMOS dados, da MESMA fonte — o `ctx.state` é o
    `state_full` —, e o que faltava era o objeto que os apresenta com os nomes
    que o dono da frase conhece. É a ponte inteira: nenhuma regra de texto se
    reescreve deste lado.
    """

    _alvo_de_edicao: Any
    _edit_target_uniq: str | None
    _edit_target_label: str | None
    _target_uniq_by_index: dict[int, str | None]
    _modo_nativo_ligado: bool
    _coop_ligado: bool

    __slots__ = ("_alvo_de_edicao", "_coop_ligado", "_edit_target_label",
                 "_edit_target_uniq", "_modo_nativo_ligado", "_target_uniq_by_index")

    def _edit_uniq(self) -> Any:
        """O alvo de edição — EMPRESTADO do dono, não reescrito aqui."""
        return _o_dono_da_frase()._edit_uniq(self)

    def _uniqs_conectados(self) -> list[str]:
        """Os MACs da mesa na ordem do índice — EMPRESTADO do dono (R-14)."""
        return list(_o_dono_da_frase()._uniqs_conectados(self))

    def _quantos_recebem_o_desenho(self) -> int:
        """Quantos controles este clique atinge — PERGUNTADO ao dono."""
        return int(_o_dono_da_frase()._quantos_recebem_o_desenho(self))


def _janela_do_desfecho(ctx: Contexto, uniq: str, rotulo: str = "") -> Any:
    """Um `_Janela` com o estado DESTA mesa, para a frase do desfecho."""
    from hefesto_dualsense4unix.app.alvo_de_edicao import definir_alvo

    janela = _Janela()
    definir_alvo(janela, uniq or None, rotulo or None)
    janela._target_uniq_by_index = {
        int(c.get("index") or i): (str(c.get("uniq") or "") or None)
        for i, c in enumerate(ctx.conectados)}
    janela._modo_nativo_ligado = bool(ctx.state.get("native_mode"))
    janela._coop_ligado = o_coop_manda(ctx.state)
    return janela


def _nome_da_coluna(ctx: Contexto, uniq: str) -> str:
    """O rótulo daquele controle para a frase de guardado — o nome VIVO da mesa."""
    casa = _da_mesa(ctx, uniq)
    return str(casa.get("nome") or "")


def _textos_do_desfecho(brilho: float | None, apagando: bool) -> tuple[str, str]:
    """O par (assunto, frase feliz) daquele gesto — e os quatro saem da GTK."""
    from hefesto_dualsense4unix.app.actions import lightbar_actions

    if apagando:
        return (str(lightbar_actions._ASSUNTO_APAGAR),
                str(lightbar_actions._TOAST_LIGHTBAR_APAGADA))
    pct = 100 if brilho is None else round(brilho * 100)
    return (str(lightbar_actions._ASSUNTO_COR).format(pct=pct),
            str(lightbar_actions._TOAST_COR_ENVIADA).format(pct=pct))


_DO_PERFIL: Any = object()


def _escrever_a_cor(ctx: Contexto, p: Any, uniq: str,
                    rgb: tuple[int, int, int], *,
                    apagando: bool = False,
                    escolha: bool = False,
                    brilho: Any = _DO_PERFIL) -> str | None:
    """O CAMINHO ÚNICO de escrita de cor desta aba — com o brilho e com a frase.

    **E COM A GUARDA DE COR ÚNICA, desde 08/09/2026.** Ela morava só no gesto
    `cor`, e o `reenviar` — que manda ao aparelho o hexa que está na caixa —
    passava por fora: a segunda porta de escolha de cor não tinha a regra que
    a primeira tinha. A guarda mudou de lugar para CÁ justamente porque esta
    docstring já prometia uma porta só; ou a promessa vale para a regra
    também, ou ela era meia verdade.

    `escolha=True` é quem a liga, e são os dois gestos em que ela ESCOLHE um
    tom (`cor` e `reenviar`). Os outros dois passam por fora com razão
    escrita: `apagar` manda preto, que é ausência de cor e não colide com
    nada; e `brilho` reenvia a cor que o controle JÁ TEM com outro fator — ali
    a cor não é uma escolha nova, e deslocá-la faria um arraste de brilho
    trocar a cor dela sem que ela tenha pedido.

    :return: o RECADO quando a cor pedida foi deslocada, senão `None`.

    O `brilho` CHEGA PRONTO OU SE PERGUNTA AO PERFIL, e o parâmetro nasceu em
    03/09/2026 com o trilho que grava. Os três gestos de COR não têm brilho na
    mão — eles pintam com o que já está guardado —, e para eles nada muda: o
    default `_DO_PERFIL` lê `brilho_aceso`, que é o MESMO número que a
    coluna imprime. Quem passa o valor é o gesto `brilho`, e a razão é de ORDEM:
    ele precisa aplicar no aparelho o número que ela ACABOU de escolher, e não
    depender de a gravação em disco ter acontecido primeiro. Sem o parâmetro,
    "aplicar" e "guardar" ficariam presos numa ordem só — e um disco que
    recusasse a escrita levaria junto a aplicação, que não tem nada a ver.

    ELE É O `_aplicar_cor_no_controle` DA GTK, no que esta tela pode ter
    (`app/actions/lightbar_actions.py`). Duas coisas que faltavam, e as duas
    estavam medidas:

    **1. O BRILHO VIAJA JUNTO.** A linha era `p.led_set(rgb, uniq=uniq)`, sem o
    argumento — e o `_payload_led_set` só põe o campo quando ele é passado, então
    o `led.set` do daemon caía no default *"Ausente ou inválido -> assume 1.0"*
    (`ipc_handlers._handle_led_set`). Consequência na tela dela: a mesma coluna
    que mostra `50%` no trilho mandava a cor a 100%, e um clique num tom
    DESFAZIA o brilho que ela tinha escolhido na janela GTK — sem uma palavra.
    A GTK manda `brightness=self._current_brightness` em toda escrita
    (`lightbar_actions.py`); aqui o número sai de `brilho_aceso`, que
    é o MESMO que a coluna imprime.

    **2. O DESFECHO SE LÊ DO CORPO DO DAEMON.** A porta era `led_set` (`bool`), e
    um `True` dele significa só *"o daemon respondeu"*. O corpo do `led.set`
    publica `aplicado_em`/`guardado_em` desde a APLICAR-VERDADE-01, e
    `led_set_detalhado` já os entregava — sem um chamador em `interface/` até
    hoje. Sem eles, um clique com o Modo Nativo ligado (o backend muta toda
    escrita de output) ou com o controle recém-saído da mesa saía **calado**: o
    piloto anotava "aplicou", a barra não mudava, e o segundo clique parecia o
    primeiro. É o defeito que esta casa nomeia como o mais caro.

    QUEM DECIDE A FRASE É `textos_de_aplicacao.frase_do_desfecho`, e só ele —
    `frase_do_envio` o chama e troca *"aplicado"* por *"enviada"* no ramo feliz,
    porque por Bluetooth o firmware ACEITA E IGNORA escritas de cor (a medição
    está em `_TOAST_COR_ENVIADA`, 330 mil escritas ignoradas com a barra
    apagada). Nada de texto nasce deste lado.

    POR QUE O `RuntimeError` NO RAMO DO GUARDADO, e ele não é "recusa": entre a
    frase no cartão e o silêncio, o silêncio é a mentira — quem clica conclui
    que a cor foi. A GTK diz a mesma frase num toast neutro.

    **FATO SUBSTITUÍDO — 04/09/2026.** Estas linhas diziam que *"o único canal
    que esta tela tem é o `_recusou_dizendo`, e ele só carrega `RuntimeError`"*,
    com um RELATO pedindo um canal de aviso. **O canal existe:** a ONDA0-P o
    entregou com a D-01, e um gesto que devolve `{"recado": …}` pousava no MESMO
    cartão com tom de sucesso e vida de 6 s — o `brilho` desta aba o usa. Desde
    13/09/2026 essa frase vai ao diário da janela e não à tela (TELA-CALADA-01 e
    FRASES-E-DICAS-01).

    **E MESMO ASSIM ELE NÃO SERVE AQUI**, e a razão não é de infraestrutura:
    este caminho **não sabe qual dos dois desfechos aconteceu**. Quem lê o corpo
    do daemon é `frase_do_desfecho`, e o que volta é UMA frase — as quatro
    razões (recusa explicada, aplicado, guardado, nada aconteceu) chegam aqui já
    colapsadas em texto. Escolher o tom exigiria reler `destinos_da_aplicacao`
    deste lado, que é a segunda verdade sobre o mesmo payload, e é exatamente o
    que a ELO-MUDO-01 inverteu. Enquanto o dono não separar os dois, o laranja é
    o erro mais barato: diz demais sobre um guardado, e não de menos sobre uma
    recusa. **RELATO:** um segundo retorno de `frase_do_desfecho`, dizendo QUAL
    dos quatro destinos venceu, fecharia isto para as dez abas — é
    `app/textos_de_aplicacao.py`, fora do território deste arquivo.

    A COMPARAÇÃO É COM A FRASE FELIZ, e não com `aplicado_em`: quem lê os dois
    destinos é `frase_do_desfecho`, que conhece as QUATRO razões do daemon e a
    ordem entre elas — recusa explicada, aplicado, guardado, nada aconteceu.
    Reler `destinos_da_aplicacao` deste lado para decidir seria a segunda
    verdade sobre o mesmo payload, e é exatamente o que a ELO-MUDO-01 inverteu:
    *"antes a janela deduzia e o daemon era ignorado"*. Aqui a janela só
    pergunta *"a frase que saiu é a do caminho feliz?"* — e cala quando é.
    """
    from hefesto_dualsense4unix.app.actions.lightbar_actions import frase_do_envio

    recado: str | None = None
    if escolha:
        rgb, recado = _sem_repetir_a_cor_do_vizinho(ctx, uniq, rgb)
    cru: dict[str, Any] | None = None
    if brilho is _DO_PERFIL:
        cru = perfil.ativo_que_vale(ctx.state.get("active_profile"))
        brilho = brilho_aceso(ctx.por_uniq(uniq), cru, uniq)
    #: 0% do controle sai do disco junto (`_guardar_a_cor_no_perfil`).
    religar = bool(escolha and brilho is not None and float(brilho) <= 0.0)
    if religar:
        brilho = _o_brilho_de_religar(
            cru if cru is not None else perfil.ativo_que_vale(ctx.state.get("active_profile")),
            uniq)
    corpo = p.led_set_detalhado(rgb, brightness=brilho, uniq=uniq)
    if corpo is None:
        raise RuntimeError(sem_resposta_do_daemon())
    assunto, enviado = _textos_do_desfecho(brilho, apagando)
    frase = frase_do_envio(assunto, enviado, corpo,
                           _janela_do_desfecho(ctx, uniq, _nome_da_coluna(ctx, uniq)))
    if frase != enviado:
        raise RuntimeError(frase)
    if escolha:
        _guardar_a_cor_no_perfil(ctx, uniq, rgb, religar=religar)
    elif apagando:
        _guardar_o_apagado_no_perfil(ctx, uniq)
    return recado


def _o_brilho_de_religar(cru: dict[str, Any] | None, uniq: str) -> float:
    """O brilho em que a cor escolhida acende uma barra apagada.

    A-04-PERGUNTA-AO-DAEMON-VIVO-01. É o que o perfil ATIVO dá a este controle
    (`brilho_do_controle`: o brilho próprio dele, ou o do perfil) — e é
    também o que o disco guarda depois do gesto (`_com_a_cor_gravada`), para
    o perfil reaplicado acender o mesmo. Quem apagou pelo «Desligar» neste
    perfil tem o 0% gravado, e aí vale o do perfil, que ele herda quando o 0%
    sai. Conferência, 25/09/2026: o «Desligar» feito num perfil atravessa a
    troca automática pela camada viva, e o perfil do jogo pode guardar um
    brilho próprio para este controle — ler só o do perfil acendia a barra no
    brilho errado e APAGAVA do disco o brilho que ela tinha gravado ali.
    Perfil a 0% (a mesa inteira apagada) ou sem o campo legível acende cheio:
    a cor escolhida tem de aparecer.
    """
    leds = (cru or {}).get("leds") if isinstance(cru, dict) else None
    try:
        do_perfil = float(leds.get("lightbar_brightness", 1.0)) if isinstance(
            leds, dict) else 1.0
    except (TypeError, ValueError):
        do_perfil = 1.0
    for candidato in (brilho_do_controle(cru, uniq), do_perfil):
        if candidato is not None and 0.0 < candidato <= 1.0:
            return candidato
    return 1.0


def _guardar_o_apagado_no_perfil(ctx: Contexto, uniq: str) -> None:
    """O «Desligar» vai ao disco como o BRILHO em 0% deste controle, e a cor fica.

    A-04-PERGUNTA-AO-DAEMON-VIVO-01, 25/09/2026. Ele gravava o preto como a
    COR do controle, e desde 22/09 o preto não é cor (`led_control.cor_escolhida`,
    a ordem dela: *"vamos banir esse preto de aparecer"*): o perfil
    reaplicado lia «não opinou» e acendia a barra de novo. Medido na mesa de
    quatro real: o P2 apagado voltava vermelho na troca manual, no boot e no
    «Salvar Perfil» — e o preto tinha apagado do disco o laranja que ela
    escolhera. O caminho de apagar que a própria decisão de 22/09 deixou é o
    brilho, *"um campo que só a mão dela move"*.

    Os mesmos dois estados sem onde gravar de `_guardar_a_cor_no_perfil`, e a
    mesma razão para sair calado: a barra já apagou.
    """
    nome = perfil.nome_do_ativo(ctx.state).strip()
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    with contextlib.suppress(OSError):
        gravar_pelo_gesto("luz", nome, lambda prof: _com_o_brilho_gravado(prof, uniq, 0),
                          uniq=uniq, origem="interface-nova")


def _guardar_a_cor_no_perfil(ctx: Contexto, uniq: str,
                             rgb: tuple[int, int, int], *,
                             religar: bool = False) -> None:
    """A cor que ela ESCOLHEU vai ao disco, no override daquele controle.

    **O DEFEITO QUE ISTO MATA, medido na bancada dela em 09/09/2026**, e ele
    tinha duas caras que ela viu como uma só — *"o controle branco fica
    oscilando entre a cor que eu seleciono e a cor azul. fora que o slicer tá
    estranho ainda"*:  # noqa-acento: citação literal

        no disco, o override do branco  {"leds": {"lightbar_brightness": 0.49}}
        a cor que ela escolheu           em lugar NENHUM

    `_escrever_a_cor` mandava a cor só ao daemon (`led_set_detalhado`), que a
    guarda na camada VIVA por-uniq. Ela acende, e some no primeiro evento que
    faça o resolvedor reler o perfil — replug, `profile.switch`, reaplicação.
    O que sobra embaixo é a camada automática, `player_slot_color(1)` =
    `#0000FF`, ou o global dela, `#2850B4`: **os dois são azuis**, e é o azul
    que ela via voltar.

    E ERA A MESMA RAIZ DO TRILHO. Sem cor no disco, o gesto `brilho` só podia
    adivinhar a cor pela luz ACESA — que já vem escalada (D8) — e reescalá-la:
    medido, `#2850B4` a 80% -> 60% -> 70% -> 80% desceu para `(19,38,86)`,
    `(13,26,60)`, `(10,20,48)`. **Subindo o brilho, a cor escurecia**, até
    morrer no preto. Ver a escada nova em `brilho`.

    ERA UM CAMINHO SÓ, E FECHADO — 08/09/2026: `_com_a_cor_gravada` já
    existia, já carimba a PROCEDÊNCIA (`lightbar_para_o_numero`) que
    `cores_sem_colisao` lê para não fossilizar a escolha dela, e tinha UM
    chamador — desligar o automático. A escolha de um tom nunca passou por
    ele.

    QUEM GRAVA A COR É QUEM A ESCOLHE: um tom (`cor`, `reenviar` —
    `escolha=True`). O «Desligar» gravava o preto aqui até 25/09/2026, e o
    preto não é cor desde 22/09: ele grava o brilho em 0%, em
    `_guardar_o_apagado_no_perfil`, e a cor dela fica. O `brilho` passa por
    fora de propósito: ele não escolhe cor, e gravar ali faria um arraste de
    trilho congelar no perfil uma cor que ela não pediu.

    `religar` é a cor escolhida numa barra em 0%: o 0% do controle sai do
    override junto, e ele volta ao brilho do perfil — o mesmo em que o
    `_escrever_a_cor` acabou de acendê-la.

    SEM PERFIL NO DISCO NÃO HÁ ONDE GUARDAR, e o gesto sai calado: a cor JÁ
    está no aparelho, que é o que ela pediu, e um cartão de recusa depois do
    ato diria que o produto não fez o que fez. É o mesmo estado que o gesto
    `brilho` recusa na ENTRADA, antes de qualquer escrita — lá dá para
    recusar, aqui já não.

    **SÃO DOIS ESTADOS, E O SEGUNDO APARECEU NA PRÓPRIA LEVA:** o
    `active_profile` VAZIO, e o `active_profile` que nomeia um perfil que o
    disco não tem (`FileNotFoundError: perfil não encontrado`). Sete réguas
    desta aba caíram nele no minuto em que esta função nasceu — elas montam
    um contexto com perfil ativo e não semeiam arquivo nenhum, que é
    exatamente a forma do estado real. **A gravação é a SEGUNDA metade deste
    gesto e não pode derrubar a primeira**, que já chegou ao plástico dela.

    O `except` É ESTREITO DE PROPÓSITO — só `OSError`, que é o que o disco
    tem a dizer. Um `except Exception` engoliria o `ValidationError` de um
    perfil malformado, e aí a cor sumiria do arquivo em silêncio, que é o
    defeito que esta função nasceu para matar.
    """
    nome = perfil.nome_do_ativo(ctx.state).strip()
    dele = next((c for c in ctx.conectados
                 if str(c.get("uniq") or "") == uniq), None)
    numero = _numero(ctx, dele) if dele is not None else None
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    with contextlib.suppress(OSError):
        gravar_pelo_gesto(
            "luz", nome,
            lambda prof: _com_a_cor_gravada(prof, uniq, rgb, numero, religar=religar),
            uniq=uniq, origem="interface-nova")


def _a_cor_guardada(cru: dict[str, Any] | None,
                    uniq: str) -> tuple[int, int, int] | None:
    """A cor que o PERFIL guarda para este controle, ou `None` se não há."""
    dono = ((cru or {}).get("controllers") or {}).get(chave_do_override(uniq))
    rgb = ((dono or {}).get("leds") or {}).get("lightbar")
    if not rgb or len(tuple(rgb)) < 3:
        return None
    r, g, b = tuple(rgb)[:3]
    from hefesto_dualsense4unix.core.led_control import cor_escolhida as a_cor_nao_e_o_preto

    return a_cor_nao_e_o_preto((int(r), int(g), int(b)))


def _a_cor_guardada_que_vale(ctx: Contexto, cru: dict[str, Any] | None,
                             c: dict[str, Any]) -> tuple[int, int, int] | None:
    """A cor gravada DESTE controle — ou `None` quando ela é FÓSSIL."""
    from hefesto_dualsense4unix.core.led_control import (
        LEGADO,
        PecaDaMesa,
        fosseis,
        player_slot_color,
    )
    from hefesto_dualsense4unix.interface.cartao_do_controle import cor_do_swatch

    uniq = str(c.get("uniq") or "")
    guardada = _a_cor_guardada(cru, uniq)
    if guardada is None:
        return None
    dono = ((cru or {}).get("controllers") or {}).get(chave_do_override(uniq))
    para = ((dono or {}).get("leds") or {}).get("lightbar_para_o_numero")
    numero = _numero(ctx, c)
    procedencia = LEGADO if para is None else para
    if not automatico_do_perfil(cru):
        sem_paleta = PecaDaMesa(uniq=uniq, pedida=guardada, do_numero=None,
                                procedencia=procedencia, numero=numero)
        luz = _o_tom_que_acende(cor_do_swatch(c), brilho_aceso(c, cru, uniq))
        return None if luz is not None and uniq in fosseis([sem_paleta]) else guardada
    mesa = [PecaDaMesa(uniq=uniq, pedida=guardada,
                       do_numero=player_slot_color(numero),
                       procedencia=procedencia, numero=numero,
                       do_plastico=_tom_do_plastico(c))]
    for outro in ctx.conectados:
        dele = str(outro.get("uniq") or "")
        if dele and dele != uniq:
            mesa.append(PecaDaMesa(uniq=dele, pedida=None,
                                   do_numero=player_slot_color(_numero(ctx, outro)),
                                   numero=_numero(ctx, outro),
                                   do_plastico=_tom_do_plastico(outro)))
    return None if uniq in fosseis(mesa) else guardada


def _tom_do_plastico(c: dict[str, Any]) -> tuple[int, int, int] | None:
    """O tom de luz do plástico deste controle — o mesmo dono do daemon.

    O `state_full` publica o `modelo` (o nome de fábrica que o aparelho
    respondeu), e a mesa da tela carrega a `cor` (o `id` da linha do mapa).
    Qualquer dos dois vai a `cor_do_plastico.tom_da_luz`, a regra que o
    provider do daemon usa. `None` quando o plástico não foi lido ou não tem
    tom, e a cor automática é a do número.
    """
    from hefesto_dualsense4unix.integrations.cor_do_plastico import (
        tom_da_luz_do_nome,
    )

    for chave in ("modelo", "cor"):
        tom = tom_da_luz_do_nome(str(c.get(chave) or ""))
        if tom is not None:
            return tom
    return None


def _a_cor_do_global(cru: dict[str, Any] | None) -> tuple[int, int, int] | None:
    """A cor GLOBAL do perfil (`leds.lightbar`), antes do brilho — ou `None`."""
    from hefesto_dualsense4unix.core.led_control import (
        cor_escolhida as a_cor_nao_e_o_preto,
    )

    leds = (cru or {}).get("leds") if isinstance(cru, dict) else None
    rgb = leds.get("lightbar") if isinstance(leds, dict) else None
    if not rgb or len(tuple(rgb)) < 3:
        return None
    try:
        r, g, b = (int(c) for c in tuple(rgb)[:3])
    except (TypeError, ValueError):
        return None
    return a_cor_nao_e_o_preto((r, g, b))


# viu: o controle branco oscilando entre a cor dela e o azul, porque a escolha
@gesto("04-iluminacao.html", "cor", grava="gravar_pelo_gesto")
def cor(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Ela clicou num tom. A cor vai AO CONTROLE NA HORA.

    DECISÃO DELA, 01/09/2026: *"clicar na cor já deveria aplicar a cor no
    controle."* Isso decide o modelo da interface inteira, e não só deste botão:
    **o gesto age na hora**, e não junta mudanças num rascunho à espera de um
    "Aplicar".

    A GUI estável tem as duas rotas — o `led.set` direto e o
    `profile.apply_draft` do rascunho — e o próprio `on_lightbar_apply` chama a
    primeira de "a cor já acende ao soltar o seletor". Aqui a primeira é a
    regra, e o "Salvar Perfil" continua sendo o que grava.

    A CONVERSÃO NÃO MORA AQUI, e morava até 02/09/2026. A linha era::

        p.led_set(tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4)), uniq=uniq)

    Isso é `core/led_control.hex_to_rgb`, que já existia, que este arquivo já
    alcançava (ele importa `player_slot_color` do mesmo módulo) e que **RECUSA
    DIZENDO**: `ValueError` com a razão escrita — *"hex_to_rgb espera formato
    RRGGBB"*, *"componente não numérico"*.

    UMA PORTA SÓ, DESDE 11/09/2026 — e eram DUAS. A segunda era o seletor de
    cores do sistema, a casa hachurada no fim da fileira: ela não trazia
    `data-hex`, e a cor vinha no `valor` que o ouvinte lia do campo. Ela saiu
    por ordem dela (ver :data:`FORA_DA_GUIA`, a mesma decisão), e a queda pelo
    `valor` saiu junto — **peça sem chamador é o que o portão `casa-sabe`
    acusa, e peça com chamador e sem tela é pior**: um caminho que nenhum
    elemento da página alcança aceita, calado, carga que ninguém desenhou.

    O QUE MORREU JUNTO, e fica escrito porque custou uma medição em
    02/09/2026: a guarda `_so_abriu_o_seletor` era chamada AQUI porque um campo
    de cor dispara `click` ao ABRIR, com o valor velho, e `change` quando ela
    confirma. Medido com o BOOTSTRAP real dentro de um Chrome::

        ela ABRE     {gesto:'cor', hex:'', valor:'#0000ff', tipo:'input',
                      evento:'click'}
        ela ESCOLHE  {gesto:'cor', hex:'', valor:'#12ab34', tipo:'input',
                      evento:'change'}

    Sem a guarda, abrir e CANCELAR deixava a barra dela numa cor que ela nunca
    pediu. **A guarda continua viva** — o `brilho` e o `auto-cores` a chamam
    pelo mesmo motivo, com o tempo invertido —, mas não aqui: um botão da guia
    não abre nada.

    SEM `hex`, RECUSA DIZENDO. Todo botão da fileira nasce com `data-hex`, e
    um pedido sem ele não vem da tela: é carga inventada ou endereço que
    envelheceu. Sair calado esconderia o defeito; adivinhar pelo `valor`
    ressuscitaria a porta que ela mandou fechar.

    E O DESFECHO SE LÊ — 02/09/2026. A linha era `p.led_set(...)` sem olhar o
    retorno; ver `sem_resposta_do_daemon` para o que isso custava.

    E O BRILHO VIAJA JUNTO — 03/09/2026. Ver `_escrever_a_cor`: até aqui este
    gesto DESFAZIA o brilho dela a cada clique num tom.

    E DUAS PEÇAS NUNCA FICAM DA MESMA COR — 08/09/2026. O alvo aqui é UM
    controle, então escolher o tom que o vizinho já tem é uma escolha e não um
    broadcast: `_escrever_a_cor(..., escolha=True)` devolve a frase que diz DE
    QUEM é a cor. Vale também para o `reenviar`, que passa pela mesma porta
    desde que a guarda mudou de lugar.
    """
    from hefesto_dualsense4unix.core.led_control import hex_to_rgb

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("cor: o clique não disse em qual controle")
    pedido = str(o.get("hex") or "")
    if not pedido:
        raise ValueError(
            "cor: o clique não disse qual tom. Todo botão da fileira manda o "
            "próprio hex; quem mandava a cor por outro campo era o seletor de "
            "cores do sistema, que saiu da guia em 11/09/2026")
    recado = _escrever_a_cor(ctx, p, uniq, hex_to_rgb(pedido), escolha=True)
    return {"recado": recado} if recado else None


def _sem_repetir_a_cor_do_vizinho(
    ctx: Contexto, uniq: str, rgb: tuple[int, int, int]
) -> tuple[tuple[int, int, int], str | None]:
    """A cor que ESTE controle recebe, e a frase quando ela não é a pedida."""

    # vazio é o DONO (`perfil.ativo` pergunta ao `nome_do_ativo` quando o
    cru = perfil.ativo_que_vale(ctx.state.get("active_profile"))
    casas = as_casas_da_mesa(_as_pecas_da_mesa(ctx, cru))
    outros = os_outros_donos(casas, a_chave_da_cor(rgb), uniq)
    if not outros:
        return rgb, None
    raise RuntimeError(
        f"O {outros[0]['nome']} já está nesse tom: duas peças nunca ficam da "
        f"mesma cor. Nada mudou — escolha outro tom.")


def _as_pecas_da_mesa(ctx: Contexto, cru: dict[str, Any]
                      ) -> list[dict[str, Any]]:
    """Uma peça por controle ligado, na forma que `as_casas_da_mesa` lê."""
    pecas = []
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        casa = _da_mesa(ctx, uniq)
        pecas.append({
            "quem": uniq,
            "cor": _a_cor_de_agora(ctx, cru, c),
            "nome": _quem_e(ctx, c),
            "numero": _numero(ctx, c),
            "plastico": plastico_da_linha(str(casa.get("cor") or "")),
        })
    return pecas


def _quem_e(ctx: Contexto, c: dict[str, Any]) -> str:
    """Como a tela chama ESTE controle numa frase — "P2", ou o modelo dele."""
    modelo = str(_da_mesa(ctx, str(c.get("uniq") or "")).get("nome") or "").strip()
    numero = f"P{_numero(ctx, c)}"
    return f"{numero} ({modelo})" if modelo else numero


@gesto("04-iluminacao.html", "apagar", grava="gravar_pelo_gesto")
def apagar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Desligar": o brilho da barra vai a 0%, e a cor dela fica.

    NÃO é `lightbar.reset` — esse devolve a cor AUTOMÁTICA, que é o outro botão.
    Apagar e voltar ao automático são coisas diferentes, e o desenho dela as
    separa em dois botões de cores diferentes.

    E O DESFECHO SE LÊ, pelo mesmo motivo do `cor` — ver
    `sem_resposta_do_daemon`. Aqui o silêncio enganava mais: "Desligar" sem
    resposta deixa a barra ACESA, que é exatamente a cara de "não cliquei
    direito".

    O APAGADO É O BRILHO, E NÃO A COR — 25/09/2026, decisão por delegação
    (`D-2509-O-DESLIGAR-E-O-BRILHO-EM-ZERO`, A-04-PERGUNTA-AO-DAEMON-VIVO-01).
    O preto ia ao disco como a cor do controle, e desde 22/09 o preto é
    «não opinou»: a troca manual, o boot e o «Salvar Perfil» acendiam a barra
    de novo, e o laranja que ela tinha escolhido estava perdido. O brilho em
    0% é o apagar que a decisão de 22/09 deixou, e sobrevive a reaplicar o
    perfil (`_guardar_o_apagado_no_perfil`). Para acender: o trilho, ou um tom
    da guia (`_escrever_a_cor`, `religar`).

    PELO MESMO CAMINHO DE ESCRITA, com o brilho 0 no parâmetro: o preto que
    sai é `int(c * 0)`, e o daemon guarda o 0% ao lado dele — é o que o
    trilho desta coluna passa a mostrar.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("apagar: o clique não disse em qual controle")
    _escrever_a_cor(ctx, p, uniq, (0, 0, 0), apagando=True, brilho=0.0)


@gesto("04-iluminacao.html", "reenviar", grava="gravar_pelo_gesto")
def reenviar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A caixa `#RRGGBB` é o botão: a cor que está escrita vai ao controle de novo.

    DECISÃO DELA, 04/09/2026, na pergunta [03] desta aba, contra as outras duas
    opções que eu ofereci (deixar como está, ou um terceiro botão em Opções):
    *"A caixa do hexadecimal vira o botão."*

    O BURACO QUE ISSO FECHOU era o do seletor de cores do sistema: um
    `<button>` da guia sempre dispara, então clicar de novo no mesmo tom
    reenvia; aquele campo não — ele só avisava no `change`, e reabri-lo para
    confirmar a MESMA cor não mandava nada ao aparelho (ver
    `_so_abriu_o_seletor`, que é quem descarta o `click` de abertura, e tem de
    descartar). A cor que ela escolhia à mão era justamente a única sem porta
    de volta.

    **A PORTA QUE ABRIU O BURACO SAIU EM 11/09/2026** (:data:`FORA_DA_GUIA`), e
    este botão FICA — a decisão [03] dela não caducou com ela. O que ele serve
    agora é a cor que a fileira não tem: o global do perfil dela, um dos três
    tons podados que um perfil antigo ainda guarda, ou simplesmente um controle
    que caiu e voltou e ela quer conferir se a cor chegou. A janela GTK tinha
    um botão dedicado para isso.

    O VALOR VEM DO `texto`, e não de um `data-hex`, e essa é a parte que
    importa: `data-hex` é escrito pelo GERADOR e fica congelado no que o mockup
    sabia — reenviar por ele mandaria ao plástico dela a cor do desenho. O
    `textContent` desta caixa é reescrito a cada tique pelo `data-campo="hex"`,
    com a cor PEDIDA (pré-escala de brilho — ver `cor_escolhida`), então o que
    sai daqui é exatamente o que ela está lendo na tela.

    NÃO É UM SEGUNDO CAMINHO DE ESCRITA. Ele passa pelo `_escrever_a_cor` como
    os outros três, então herda o brilho do perfil, a leitura do desfecho **e a
    guarda de cor única**. Uma chamada direta ao `led_set` aqui reintroduziria,
    nesta porta, os dois defeitos que aquele caminho único nasceu para curar.

    **A GUARDA CHEGOU AQUI EM 08/09/2026, e antes não estava.** O `cor` a
    tinha e este não — a caixa do hexadecimal alcança o tom EXATO de outra
    coluna (é literalmente o texto que a outra coluna imprime), então esta era
    a porta mais barata para pôr duas peças da mesma cor. A frase acima já
    dizia "passa pelo `_escrever_a_cor` como os outros"; a regra passou a
    estar lá dentro para a frase ser verdade inteira.

    O TRAVESSÃO É RECUSA. Numa coluna que esvaziou, o molde do lugar sem dono
    escreve `—` nesta caixa; a folha desta aba já lhe tira o clique
    (`pointer-events:none`), e esta guarda é a segunda trava — a que vale se
    alguém alcançar o gesto por outro caminho. `hex_to_rgb` recusaria dizendo,
    mas com uma frase que fala de formato, não do que aconteceu.
    """
    from hefesto_dualsense4unix.core.led_control import hex_to_rgb

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("reenviar: o clique não disse em qual controle")
    escrito = str(o.get("texto") or "").strip()
    if not escrito or not escrito.startswith("#"):
        raise ValueError(
            f"reenviar: a caixa do hexadecimal não tem uma cor a reenviar "
            f"({escrito!r}) — este lugar está sem controle.")
    recado = _escrever_a_cor(ctx, p, uniq, hex_to_rgb(escrito), escolha=True)
    return {"recado": recado} if recado else None


# da barra ao jogo (`lightbar.reset` — o `ipc_handlers` diz com todas as letras
# `profile.switch` chama `clear_manual_trigger_active()` SEM argumento
# desta aba passa por ele em todo clique (`perfil.gravar_e_reaplicar`). O que se


def _pct_pedido(o: dict[str, Any]) -> int:
    """Os 0-100 que o trilho mandou, validados PELO ESQUEMA e não por mim.

    A FAIXA TEM DONO: `app/draft_config.LedsDraft.lightbar_brightness` é
    `int, ge=0, le=100` — o mesmo campo que o `GtkScale` da janela estável
    alimenta. Digitar `0 <= n <= 100` aqui seria a segunda declaração da mesma
    faixa, e a que envelheceria calada no dia em que o produto mudasse a escala.
    Aqui só se traduz a recusa do pydantic para uma frase de tela.

    `valor` É A PORTA, e é o que o BOOTSTRAP manda de todo elemento que tem
    `value` — num `<input type="range">` é a posição do polegar, como string.
    """
    from hefesto_dualsense4unix.app.draft_config import LedsDraft

    cru = str(o.get("valor") or "").strip()
    try:
        return int(LedsDraft(lightbar_brightness=int(float(cru))).lightbar_brightness)
    except (TypeError, ValueError) as erro:
        raise ValueError(
            f"brilho: o trilho mandou {cru!r}, que não é uma porcentagem de "
            f"0 a 100 ({erro})") from erro


def _fracao_do_disco(pct: int) -> float:
    """Os 0-100 da TELA na escala em que o PERFIL guarda o brilho (0.0-1.0).

    A CONTA TEM DONO, e ela é `app/draft_config._leds_draft_to_config` — o
    `leds.lightbar_brightness / 100.0` que o "Salvar Perfil" da janela estável
    já faz com o mesmo número. As duas escalas convivem de propósito e estão
    declaradas nos dois esquemas: `LedsDraft` é `int 0-100` (é o que a tela
    mostra) e `LedsConfig` é `float 0.0-1.0` (é o que o disco guarda). Digitar
    o `/100` aqui seria a terceira cópia, e a primeira a errar no dia em que a
    escala mudar.

    ELE É PRIVADO POR CONVENÇÃO DE NOME, e não por contrato — do mesmo jeito que
    este arquivo já lê `lightbar_actions._AVISO_HEFESTO_DESLIGADO`.
    **RELATADO:** a conversão entre as duas escalas merece nome público; é
    `app/draft_config.py`, fora do território deste arquivo.
    """
    from hefesto_dualsense4unix.app.draft_config import (
        LedsDraft,
        _leds_draft_to_config,
    )

    so_o_brilho = _leds_draft_to_config(LedsDraft(lightbar_brightness=pct),
                                        only_fields={"lightbar_brightness"})
    return float(so_o_brilho.lightbar_brightness)


def _com_o_brilho_gravado(prof: Any, uniq: str, pct: int) -> Any:
    """O perfil com o brilho DESTE controle trocado, ou `None` se nada mudou.

    `None` EVITA O BARULHO, e é a mesma regra do `_com_os_gatilhos` da aba
    Gatilhos: regravar um perfil idêntico troca a data do arquivo e cria um
    backup em `.historico/` por um arraste que voltou ao mesmo lugar.

    O ALVO É O OVERRIDE DO CONTROLE, e não a seção global — decisão do enunciado
    desta frente, e ela tem base medida: `ControllerOverrides.leds` existe desde
    a PERFIL-02 e `manager._controllers_to_led_scales` já distribui o brilho por
    MAC. **E esta aba não tem outro alvo possível:** a fita do topo é INERTE
    aqui desde 28/08 (decisão dela — os quatro controles ficam lado a lado e
    *"não há escolhido"*), então cada trilho pertence a UMA coluna e a uma só.
    Gravar no global faria o trilho do P2 mudar o brilho do P1, que é a mesma
    contradição que o `_janela_do_desfecho` já anota sobre o ramo "Todos".

    A FUSÃO É POR CAMPO, e o esquema a escreve: um override PARCIAL nunca apaga
    o global no replug (PERFIL-01). Por isso o ramo do `model_copy` existe — os
    overrides do disco dela HOJE são `{"lightbar": [255, 0, 0]}` e nada mais, e
    trocar a seção inteira por uma que só fala de brilho apagaria a cor que ela
    escolheu para aquele controle. `save_profile` serializa as entradas do mapa
    com `exclude_unset`, então o que não foi tocado continua ausente do arquivo.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    fracao = _fracao_do_disco(pct)
    chave = chave_do_override(uniq)
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.leds
    if antes is None:
        from hefesto_dualsense4unix.app.draft_config import (
            LedsDraft,
            _leds_draft_to_config,
        )

        novos = _leds_draft_to_config(LedsDraft(lightbar_brightness=pct),
                                      only_fields={"lightbar_brightness"})
    else:
        if antes.lightbar_brightness == fracao:
            return None
        novos = antes.model_copy(update={"lightbar_brightness": fracao})
    atuais[chave] = dele.model_copy(update={"leds": novos})
    return prof.model_copy(update={"controllers": atuais})


@gesto("04-iluminacao.html", "brilho", grava="gravar_pelo_gesto")
def brilho(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Ela arrastou o trilho. O brilho vai AO APARELHO e AO DISCO, na hora.

    DECISÃO DELA, 03/09/2026. Perguntada se mexer no brilho grava o perfil na
    hora ou espera o "Salvar Perfil": **"Grava na hora"**.

    O QUE ISSO DESFAZ, e estava na tela: o trilho JÁ ERA DESENHADO como slider —
    a regra `.cheio::after` punha um knob de 12px na ponta da barra roxa — e não
    fazia nada. Ela via `100%`, arrastava, e o número não mudava. O
    `docs/data/paridade-gtk-html.csv` a chamava de *"a maior falta desta aba"*.

    POR QUE GRAVAR É A ÚNICA SAÍDA COERENTE, e a razão é medida: esta interface
    NÃO TEM RASCUNHO (decisão dela de 01/09 — *"clicar na cor já deveria aplicar
    a cor no controle"*), e o disco é o que a troca de perfil reaplica. Sem
    gravar, o valor voltaria sozinho ao velho no primeiro perfil aplicado de
    novo, e o gesto seria mais um botão que aceita o toque e não age — a
    família de defeito que o mapa desta casa nomeia dezesseis vezes. (O número
    que a coluna imprime é o que o daemon acende, `brilho_aceso`, desde
    25/09/2026; o do disco é a queda quando ele não diz.)

    OS TRÊS TEMPOS, E A ORDEM IMPORTA:

        1. a COR PEDIDA sai da tela com o brilho VELHO — `_a_cor_de_agora`
           inverte a escala do daemon (D8: o `lightbar_rgb` é PÓS-escala), e
           invertê-la com o brilho NOVO devolveria uma cor que ela nunca pediu;
        2. o DISCO recebe o número novo. Ele é a promessa do gesto, e é o que
           sobrevive a um `profile.switch`;
        3. o APARELHO recebe a mesma cor com o brilho NOVO, passado no
           parâmetro — e não relido do disco. Assim a aplicação não depende de a
           gravação ter dado certo, e um disco cheio não apaga a barra dela.

    ESCREVE NO DISCO DELA, e por isso ele entra em `hefesto_vivo.PERIGOSOS`: a
    prova botão a botão roda aba por aba e arrastaria este trilho para o valor
    que estivesse na tela, gravando no perfil ATIVO. É o molde do `("*",
    "salvar")` e do `guardar` da aba Gatilhos, pelo mesmo motivo.

    NÃO É `perfil.gravar_e_reaplicar`, e o preço está medido em 03/09 no
    `a03_gatilhos._gravar_so_o_gatilho`: aquele caminho termina em
    `profile_switch`, que manda o daemon reaplicar o perfil INTEIRO — e a barra
    que ela tinha DESLIGADO acende de novo, sem nada na tela dizer que ia
    acontecer. Um trilho de brilho é o escopo mais estreito desta aba; ele não
    pode ser o gesto que desfaz escolha viva dela em outra célula.

    O `click` QUE VEM DEPOIS DO `change` NÃO É UM SEGUNDO PEDIDO. Medido no
    contrato do próprio ouvinte: um `<input type="range">` clicado na pista
    dispara `input`, `change` e `click`, nesta ordem, e o BOOTSTRAP escuta os
    dois últimos. Sem o guarda, um clique na pista gravaria DUAS vezes e mandaria
    DUAS escritas ao rádio. `_so_abriu_o_seletor` já era exatamente esse guarda,
    do outro lado do mesmo problema.

    SEM COR CONHECIDA, GUARDA E DIZ. Nos estados de ressalva do motor
    (a Steam segurando o `fd`, cor desconhecida) não há cor a reescalar,
    e mandar preto APAGARIA a barra por um arraste de brilho. O número vai para
    o disco — que é o que ela pediu — e o cartão diz que a barra não mudou
    agora. Entre a frase no cartão e o silêncio, o silêncio é a mentira.

    **A FRASE ENCOLHEU — 04/09/2026, decisão [04] dela**, entre três opções: a
    frase inteira, uma frase curta, e o silêncio. Ela escolheu a curta, e a
    razão que ela deu é a que este arquivo já sabia: a versão longa gastava três
    linhas de cartão *"repetindo com palavras o que a tira tracejada já mostra
    sem palavra nenhuma"*. O que saiu foi a explicação do *"porque não há cor a
    reacender"*; o que ficou é o que só a frase pode dizer — quanto foi guardado
    e qual é a causa, e a causa continua vindo do MOTOR, palavra por palavra.

    **E ELE DEIXOU DE MENTIR SOBRE O PRÓPRIO DESFECHO, no mesmo dia.** A frase
    saía por `RuntimeError`, que no piloto é o canal da RECUSA — cartão laranja,
    30 s, a mesma cara de *"o produto não fez"*. E o produto FEZ: o brilho está
    no disco dela, que é a promessa inteira deste gesto. O relato desta função
    pedia por escrito *"um canal de AVISO (nem recusa nem silêncio)"*, e a
    ONDA0-P o entregou com a D-01: um gesto que devolve `{"recado": …}` deposita
    no MESMO cartão com tom de sucesso e vida de 6 s. É o que ele faz agora —
    e o pedido some do relato porque foi atendido. Desde 13/09/2026 a frase vai
    ao diário da janela, e não mais ao cartão (TELA-CALADA-01 e
    FRASES-E-DICAS-01).

    :return: `{"recado": …}` quando o número foi guardado e a barra não pôde
        mudar; `None` no caminho feliz, em que o cartão diz a frase padrão.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("brilho: o clique não disse em qual controle")
    if _so_abriu_o_seletor(o):
        return None
    pct = _pct_pedido(o)

    nome = perfil.nome_do_ativo(ctx.state).strip()

    from hefesto_dualsense4unix.interface.cartao_do_controle import rotulo_lightbar

    dele = next((c for c in ctx.conectados if str(c.get("uniq") or "") == uniq), None)
    if dele is None:
        raise RuntimeError(
            "este controle não está ligado agora — não há barra em que "
            "aplicar o brilho.")
    antes = perfil.ativo_que_vale(nome)
    recado, _base = rotulo_lightbar(dele, ctx.state)

    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    gravar_pelo_gesto("luz", nome, lambda prof: _com_o_brilho_gravado(prof, uniq, pct),
                      uniq=uniq, origem="interface-nova")

    # {"recado": …}`: com o motor sem afirmar a cor — a Steam com o `fd`, ou
    # `player_slot_color(numero)`"*. Duas funções do mesmo arquivo, o mesmo
    # grava a escolha dela; ver `_guardar_a_cor_no_perfil`.
    alvo = _a_cor_guardada_que_vale(ctx, antes, dele) or _a_cor_de_agora(ctx, antes, dele)
    _escrever_a_cor(ctx, p, uniq, alvo, brilho=_fracao_do_disco(pct))
    if recado is not None:
        return {"recado": f"Brilho em {pct}%. {recado}."}
    return None


def _com_o_brilho_das_luzes_gravado(prof: Any, uniq: str, palavra: str) -> Any:
    """O perfil com o brilho das luzes DESTE controle trocado, ou `None`."""
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, LedsConfig

    chave = chave_do_override(uniq)
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.leds
    if antes is None:
        novos = LedsConfig.model_validate({"player_led_brightness": palavra})
    else:
        if ("player_led_brightness" in antes.model_fields_set
                and antes.player_led_brightness == palavra):
            return None
        novos = antes.model_copy(update={"player_led_brightness": palavra})
    atuais[chave] = dele.model_copy(update={"leds": novos})
    return prof.model_copy(update={"controllers": atuais})


@gesto("04-iluminacao.html", GESTO_DO_BRILHO_DAS_LUZES, grava="gravar_pelo_gesto")
def brilho_luzes(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Ela clicou numa pílula da linha LEDs: Fraco, Médio ou Forte."""
    from hefesto_dualsense4unix.core.led_control import BRILHOS_DAS_LUZES

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("brilho-luzes: o clique não disse em qual controle")
    palavra = str(o.get("luzes") or "").strip()
    if palavra not in BRILHOS_DAS_LUZES:
        raise ValueError(
            f"brilho-luzes: a pílula mandou {palavra!r}, e as palavras são "
            f"{', '.join(BRILHOS_DAS_LUZES)}")
    nome = perfil.nome_do_ativo(ctx.state).strip()
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    gravar_pelo_gesto(
        "luz", nome, lambda prof: _com_o_brilho_das_luzes_gravado(prof, uniq, palavra),
        uniq=uniq, origem="interface-nova")
    if p.player_led_brightness_set_detalhado(palavra, uniq=uniq) is None:
        raise RuntimeError(sem_resposta_do_daemon())
    return None


def _a_cor_de_agora(ctx: Contexto, cru: dict[str, Any],
                    c: dict[str, Any]) -> tuple[int, int, int]:
    """A cor que ESTE controle está acendendo agora — a que o desligamento grava.

    ELA É A PEDIDA, e não a publicada: `lightbar_rgb` vem PÓS-escala de brilho
    por contrato do daemon (D8), e gravar esse valor faria a cor do perfil
    escurecer a cada volta — a 50% de brilho, `#0000FF` viraria `#00007F` no
    disco e o brilho o escalaria de novo na aplicação seguinte. `cor_escolhida`
    é quem inverte a escala, e é o mesmo caminho que a caixa `#RRGGBB` usa.

    A QUEDA É A COR DO SLOT, e ela é a resposta CERTA e não um remendo: nos
    estados em que o motor não afirma cor (a Steam com o `fd`, cor
    desconhecida) o que o automático estava dando àquele controle era
    exatamente `player_slot_color(numero)` — é essa a paleta que ele governa. Um
    preto aqui apagaria a barra dela por um clique num interruptor; um branco
    inventaria uma cor que ninguém escolheu.

    ELA É O DONO DA MARCA DA FILEIRA — 24/09/2026, A-MARCA-DA-COR-NAO-SOME-01.
    Queixa dela: *"quando eu abaixo o volume do lightbar,. o X não permanece
    no seletor dos demais controles"*. <!-- noqa-acento: citação literal -->
    A borda na fileira do controle, o X nas fileiras dos outros, a recusa do
    tom tomado e a cor que o trilho reenvia saem TODOS daqui, e a escada é:

        1. a luz acesa, quando ela diz o tom (`_o_tom_que_acende`);
        2. a cor que ela escolheu para ESTE controle, gravada no perfil — menos
           a FÓSSIL, que o daemon já trocou pela do número
           (`_a_cor_guardada_que_vale`);
        3. com a paleta automática desligada, a cor GLOBAL do perfil, antes do
           brilho (`_a_cor_do_global`) — e, sem global, a luz acesa como está;
        4. a cor automática (`led_control.cor_automatica`): a do plástico,
           e a do número sem ela (D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO).

    O DEGRAU 1 SOZINHO NÃO SEGURAVA A MARCA, e o piloto mediu os três buracos
    com o clique: por meio segundo depois de SOLTAR o trilho o disco já tem o
    brilho novo e o daemon ainda publica a luz velha; a 0% todo tom acende
    preto; e subindo de 0% a luz velha ainda é o preto. Nos três a luz não
    diz o tom — e a cor do controle não mudou,
    porque brilho não é cor. Quem sabe a cor nessa hora é o disco (a escolha
    dela, ou o global do perfil) ou a paleta (quem nunca escolheu acende a cor
    do número). A luz continua vindo PRIMEIRO: ela é o que o plástico mostra,
    inclusive quando a cor gravada é um fóssil que o daemon trocou pela do
    número.

    O DEGRAU 3 LÊ O GLOBAL, E NÃO A LUZ — 24/09/2026, conferência desta
    frente. Ele devolvia a luz acesa como estava, e com as «Cores automáticas
    por controle» desligadas os três buracos voltavam, medidos na mesa de
    quatro real: o controle sem cor gravada perdia a borda e o X por meio
    segundo ao soltar, a 0% a marca pulava para a cor do NÚMERO, e subir do 0%
    acendia a barra na cor do número — o gesto de brilho trocando a cor. Com
    um global fora da guia (o `#2850B4` dela) o trilho ainda reenviava a luz
    já escalada, e a barra escurecia a cada arraste. A regra dela é *"nunca é
    pensada só em um modo"*.

    :param cru: o perfil como DICIONÁRIO (`perfil.ativo`), e não o `Profile` do
        pydantic: `brilho_do_controle` lê o JSON cru, e um modelo passado aqui
        devolveria `None` em silêncio — o brilho sumiria da inversão de escala e
        a cor gravada sairia escurecida.
    """
    from hefesto_dualsense4unix.core.led_control import cor_automatica
    from hefesto_dualsense4unix.interface.cartao_do_controle import cor_do_swatch

    uniq = str(c.get("uniq") or "")
    efetiva = cor_do_swatch(c)
    tom = _o_tom_que_acende(efetiva, brilho_aceso(c, cru, uniq))
    if tom is not None:
        return tom
    guardada = _a_cor_guardada_que_vale(ctx, cru, c)
    if guardada is not None:
        return guardada
    if not automatico_do_perfil(cru):
        do_global = _a_cor_do_global(cru)
        if do_global is not None:
            return do_global
        if efetiva and tuple(efetiva)[:3] != (0, 0, 0):
            r, g, b = tuple(efetiva)[:3]
            return (int(r), int(g), int(b))
    return cor_automatica(_numero(ctx, c), _tom_do_plastico(c))


def _com_a_cor_gravada(prof: Any, uniq: str, rgb: tuple[int, int, int],
                       numero: int | None = None, *, religar: bool = False) -> Any:
    """O perfil com a cor DESTE controle escrita no override dele.

    **A COR VAI COM PROCEDÊNCIA** — decisão de produto de 08/09/2026, e é o
    campo `LedsConfig.lightbar_para_o_numero`: *para qual número esta cor foi
    escolhida*. Aqui é onde ela mais importa, porque este é o momento em que
    o produto CONGELA no arquivo a cor que cada controle está acendendo — e a
    cor que ele acende agora é a do NÚMERO dele agora. Sem o carimbo, o
    arquivo guarda "azul" e perde "azul porque ele era o 1", que é a
    diferença entre uma escolha e um fóssil: o número é de SESSÃO e gira com a
    ordem de conexão. Foi assim que os ranks 2 e 4 dela ficaram com as cores
    dos slots 1 e 2, e dois DualSense acenderam o mesmo `#0000FF`.

    É O IRMÃO DE `_com_o_brilho_gravado`, campo por campo, e a razão de ser um
    segundo é a mesma que aquele documenta: **a fusão é POR CAMPO**. Um override
    do disco dela hoje é `{"lightbar": [255, 0, 0]}` e nada mais; trocar a seção
    inteira por uma que só fale de cor apagaria o brilho próprio daquele
    controle. `save_profile` serializa com `exclude_unset`, então o que não foi
    tocado continua ausente do arquivo.

    NÃO DEVOLVE `None` QUANDO NADA MUDA, ao contrário do irmão, e é de
    propósito: aqui a escrita não é o pedido dela — é a **consequência** do
    pedido, e ela tem de acontecer nas duas hipóteses. Uma cor que por acaso já
    é a do override precisa continuar lá depois de o automático sair; devolver
    `None` faria o chamador achar que não havia o que gravar naquele controle e
    seguir sem ele.

    `religar=True` é a cor escolhida numa barra em 0% (A-04-PERGUNTA-AO-DAEMON-VIVO-01):
    o brilho próprio de 0% SAI do override, e o controle volta ao do perfil —
    a mesma conta de `_o_brilho_de_religar`. Um brilho próprio ACIMA de 0 fica
    (é o de outro perfil que a camada viva atravessou apagada, e é escolha
    dela). Com o perfil em 0% e sem brilho próprio, ele fica cheio, explícito,
    pela mesma razão.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, LedsConfig

    chave = chave_do_override(uniq)
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.leds
    campos: dict[str, Any] = {"lightbar": rgb}
    if numero is not None:
        campos["lightbar_para_o_numero"] = int(numero)
    if religar:
        proprio = antes is not None and "lightbar_brightness" in antes.model_fields_set
        if antes is not None and proprio and float(antes.lightbar_brightness) <= 0.0:
            antes = LedsConfig.model_validate({
                k: getattr(antes, k) for k in antes.model_fields_set
                if k != "lightbar_brightness"})
            proprio = False
        if not proprio and float(getattr(prof.leds, "lightbar_brightness", 1.0)) <= 0.0:
            campos["lightbar_brightness"] = 1.0
    novos = (LedsConfig(**campos) if antes is None
             else antes.model_copy(update=campos))
    atuais[chave] = dele.model_copy(update={"leds": novos})
    return prof.model_copy(update={"controllers": atuais})


_RECADO_DO_AUTOMATICO_SAIU = (
    "Cores automáticas desligadas. Guardei a cor de cada controle no perfil, "
    "para nenhuma se perder e nenhuma se repetir.")

_RECADO_DO_AUTOMATICO_VOLTOU = (
    "Cores automáticas ligadas. Cada controle sem cor própria acende a cor do "
    "plástico dele, ou a do número, e duas nunca ficam iguais.")


@gesto("04-iluminacao.html", "auto-cores", grava="gravar_pelo_gesto")
def auto_cores(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O interruptor do "Cores automáticas por controle" — e ele MUDA o perfil.

    **DECISÃO DELA, 04/09/2026 (D-13), contra a recomendação escrita.** A lista
    desta aba propunha que o botão "Automático" só MOSTRASSE o estado, e que
    mudá-lo continuasse na aba Perfis. Ela recusou as duas primeiras opções e
    escolheu a terceira, com estas palavras:

        *"Um interruptor no topo da aba Iluminação."*

    Mostrar sem poder mudar é menos do que ela pediu — e o campo é o martelo
    mais pesado desta aba: ele governa a paleta automática **e** a numeração,
    inclusive a dos controles de outras marcas.

    **A CONTRADIÇÃO QUE ELE ABRE, E O CAMINHO QUE ELA ACEITOU.** A regra dela de
    03/09 é *"nenhuma cor dos controles nunca pode ser a mesma"*. Com o
    automático desligado, um controle que chega depois não tem cor própria e cai
    na cor GLOBAL do perfil — o seguinte também, e dois ficam iguais. Hoje isso
    não acontece só porque não HÁ como desligar o automático pela interface
    nova; o interruptor tira essa proteção acidental. Ofereci avisar, recusar ou
    gravar, e ela respondeu:

        *"ok aceito o caminho"*

    **Então desligar GRAVA a cor de cada controle no ato.** O automático sai,
    nenhuma cor se perde e nenhuma se repete, e o produto nunca precisa dizer
    não a ela.

    **A ORDEM É A DA GTK, e ela está medida lá:** os overrides por MAC vão
    ANTES da mudança global (`lightbar_actions._persist_leds_update`, a nota da
    R-14). Aqui os dois caem no MESMO `save_profile`, então a ordem não é de
    escrita e sim de LEITURA: a cor de cada controle é lida com o automático
    ainda valendo, que é o único instante em que ela existe para ser guardada.

    **NÃO SE DEDUZ O ESTADO DO CLIQUE, PERGUNTA-SE AO DISCO.** O `value` de um
    `<input type="checkbox">` é a string `"on"` em qualquer estado, e o piloto
    manda o `value` — não o `checked`. Ler o clique daria sempre a mesma
    resposta. O disco é a fonte que a tela já pinta a cada tique
    (`automatico_do_perfil`), então virar o que está lá é o único jeito de o
    interruptor e o perfil nunca discordarem.

    **O `click` NÃO É UM SEGUNDO PEDIDO.** Um checkbox dispara `click` e
    `change` no mesmo ato, e o BOOTSTRAP escuta os dois. Sem o guarda,
    UM clique dela viraria DUAS inversões — e o interruptor voltaria sozinho ao
    lugar, com duas gravações no perfil pelo caminho. `_so_abriu_o_seletor` já é
    exatamente esse guarda: ele descarta o `click` de todo `<input>` e deixa o
    `change`, que é o que carrega o ato.

    **REAPLICAR É METADE DO GESTO**, e sem ela ele seria o botão que aceita o
    toque e não age: `auto_player_colors` só entra em vigor na ATIVAÇÃO do
    perfil (`ProfileManager._configure_auto_player_colors`, chamado por
    `apply_profile`). `perfil.gravar_e_reaplicar` é o dono dos três tempos —
    disco, `profile.switch`, `launch_env.refresh` — e já tinha dois chamadores.

    E AQUI REAPLICAR NÃO DESFAZ ESCOLHA VIVA DELA, que é a razão pela qual o
    gesto `brilho` o recusa: as cores que o `switch` vai reaplicar são as que
    este mesmo gesto acabou de gravar, controle a controle. O que ele pinta é o
    que já estava aceso.

    :return: `{"recado": …}` — a frase que diz qual das duas metades
        aconteceu. Ela ia ao cartão verde da D-01; desde 13/09/2026 vai ao
        diário da janela.
    """
    if _so_abriu_o_seletor(o):
        return None

    nome = perfil.nome_do_ativo(ctx.state).strip()
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    cru = perfil.ativo_que_vale(nome)
    ligado = automatico_do_perfil(cru)

    def _virar(prof: Any) -> Any:
        if ligado:
            for c in ctx.conectados:
                uniq = str(c.get("uniq") or "")
                if uniq:
                    prof = _com_a_cor_gravada(
                        prof, uniq, _a_cor_de_agora(ctx, cru, c), _numero(ctx, c))
        leds = prof.leds.model_copy(update={"auto_player_colors": not ligado})
        return prof.model_copy(update={"leds": leds})

    gravar_pelo_gesto("luz", nome, _virar, origem="interface-nova")
    perfil.reaplicar(nome, ctx, p)
    return {"recado": (_RECADO_DO_AUTOMATICO_SAIU if ligado
                       else _RECADO_DO_AUTOMATICO_VOLTOU)}


_RECONCILIAR_O_COOP = "coop.sync"


def _pares_da_troca(ctx: Contexto, uniq: str, n: int) -> list[tuple[str, int]]:
    """Quem fica com que número DEPOIS da troca — o alvo e o parceiro dele.

    `identity.number.set` **PERMUTA**: o alvo vai para o número pedido e quem
    tinha aquele número fica com o do alvo, e mais ninguém se mexe. Está no
    daemon (`_set_number_locked`: *"trocar de lugar o alvo e quem tem o número
    pedido — os dois, e mais ninguém"*) e está nos dezessete lugares do desenho
    que ela aprovou (*"Os dois trocam, os outros não se mexem"*).

    POR QUE O PARCEIRO ENTRA, e ele não é zelo: as cinco lâmpadas de um
    controle preso num override velho continuariam acesas no número que o
    OUTRO acabou de receber — dois controles com o mesmo desenho, que é
    exatamente a colisão que a numeração única (R-24) existe para matar.
    Curar só o alvo trocaria uma queixa por outra, na mesma tela.

    A CONTA É DAQUI E NÃO DO DAEMON porque a resposta não a traz: o
    `identity.number.set` devolve `changed` com quem mudou de lugar, e
    `ipc_bridge.identity_number_set` reduz tudo a `(ok, motivo)`. Ler o
    `state_full` DEPOIS seria mais fiel; custa uma volta ao daemon e um dublê
    que saiba responder. **RELATADO:** uma `identity_number_set_detalhado`
    que entregue o `changed` é `app/ipc_bridge.py`, fora deste arquivo.

    Números saem de `_numero` — o dono único (`app/actions/base`), o MESMO que
    pinta a fileira de botões. Sem parceiro (número livre na mesa) a lista tem
    um par só, e é o caso da mesa de um controle.
    """
    velho = 0
    parceiro = ""
    for c in ctx.conectados:
        chave = str(c.get("uniq") or "")
        if not chave:
            continue
        numero = _numero(ctx, c)
        if chave == uniq:
            velho = numero
        elif numero == n:
            parceiro = chave
    pares = [(uniq, n)]
    if parceiro and velho:
        pares.append((parceiro, velho))
    return pares


def _acender_o_numero(ctx: Contexto, p: Any, uniq: str, n: int) -> str:
    """As cinco lâmpadas SEGUEM o número que ela acabou de escolher.

    **A QUEIXA DELA, 04/09/2026:** *"escolha do jogador no iluminação não
    funciona"*. O gesto renumerava e parava aí — e renumerar não move lâmpada
    nenhuma por conta própria. Medido na mesa dela, com os dois DualSense
    ligados e o daemon vivo, lendo `/sys/class/leds` a cada passo::

        estado de partida            slot=2 → lâmpadas do 2 · slot=1 → do 1
        1. identity.number.set       slot=1 → lâmpadas do 2 · slot=2 → do 1   ✗
        2. + led.player_set por uniq slot=1 → lâmpadas do 2 · slot=2 → do 1   ✗
        3. + coop.sync               slot=1 → lâmpadas do 1 · slot=2 → do 2   ✓

    **A LINHA 2 É O ACHADO, e ela derruba a cura óbvia.** O daemon respondeu
    `{"status":"ok","aplicado_em":["<o controle>"],"guardado_em":[]}` às DUAS
    escritas — e nenhuma lâmpada se mexeu. O byte saiu; a camada do co-op o
    repintou por cima no mesmo instante, porque no merge por campo do backend
    (`core/backend_pydualsense._merged_desired_for_key`) ela está ACIMA do
    override por-uniq::

        default global < camada AUTOMÁTICA < override por-uniq < CO-OP < jogo

    Escrever o override e ler o `aplicado_em` como sucesso teria posto na tela
    dela um "aplicado" sobre duas lâmpadas paradas — a mesma mentira que a
    MESA-CHEIA-09 mediu na janela GTK, reproduzida aqui.

    **POR QUE A CAMADA DO CO-OP FICA VELHA, e é o defeito de fundo.** Ela é um
    mapa PUBLICADO, não uma leitura: `coop._apply_coop_player_leds` calcula
    `numeros_de_jogador()` — que pergunta o número ao MESMO
    `identity_registry` que o `identity.number.set` acabou de escrever — e
    publica o resultado em `_desired_coop_by_uniq`. Só que ele roda no fim de
    um ciclo CHEIO do co-op, e um ciclo cheio pede `/dev/input` ter mudado, ou
    um grab degradado, ou `force`. Renumerar não é nenhum dos três. O
    `reassert_resolved_outputs()` que o próprio handler dispara reafirma então
    a camada VELHA, com os números de antes — e ela fica assim até o próximo
    hotplug. Na mesa dela estava assim quando esta medição começou.

    **RELATADO, e a cura estrutural é de UMA linha, no daemon:** o
    `_handle_identity_number_set` já adianta duas repinturas no ramo `changed`
    (`reassert_resolved_outputs` e `_schedule_external_tick`); falta a
    terceira, `get_coop_manager(daemon).sync(force=True)` — ou o
    `_apply_coop_player_leds` direto. É `daemon/ipc_handlers.py`, fora do
    território deste arquivo, e com ela este ramo daqui vira redundância
    barata em vez de cura.

    **OS DOIS RAMOS, e cada um trata do dono das lâmpadas naquele momento:**

    * **o co-op manda** (`o_coop_manda`: mais de um jogador na mesa) — quem
      escreve as cinco luzes é a camada dele, e a ÚNICA coisa que a move é
      recalculá-la. `coop.sync` é o gesto que o produto já tem para isso, e a
      docstring dele é explícita: *"Não liga nem desliga nada"*, *"reconciliar
      nunca ressuscita o que o jogo suspendeu"*. Escrever o override aqui
      seria escrever debaixo de quem manda;
    * **o co-op não manda** — sobra a camada automática, e ela SEGUE o número
      sozinha no `reassert` do handler… a menos que um override por-uniq esteja
      preso acima dela. É o que a janela GTK deixa para trás toda vez que ela
      usa "Desenho do PN" (`lightbar_actions._enviar_player_leds`), e ela USA a
      GTK. Aqui o override é reescrito com o padrão do número de AGORA, pelo
      dono da tabela (`core/led_control.player_led_pattern`, a mesma que o
      daemon acende e a mesma que `luzinhas` desenha nesta aba).

    **O PREÇO DO SEGUNDO RAMO, escrito porque ele é real:** um override
    por-uniq PRENDE as lâmpadas acima da camada automática, e daí em diante um
    controle que saia da mesa não faz mais os outros reacenderem sozinhos. É o
    mesmo preço que a GTK já paga desde sempre, e não há IPC que limpe o
    override (`lightbar.reset` é da barra, não das lâmpadas). Ele só se paga
    quando o co-op não manda — no ramo de cima nenhum override é escrito.

    A ORDEM É RENUMERAR PRIMEIRO, e ela decide o desfecho: o padrão das
    lâmpadas é função do número NOVO, então sem o número não há o que acender.
    E se a renumeração passar e a lâmpada não, **a renumeração VALE** — ela já
    está gravada no registro, desfazê-la seria uma segunda escrita que também
    pode falhar, e o cartão diz o que aconteceu com as luzes. O contrário —
    calar sobre a lâmpada — é o silêncio que esta casa nomeia como a mentira.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    if o_coop_manda(ctx.state):
        if not p.chamar(_RECONCILIAR_O_COOP):
            raise RuntimeError(
                f"o número deste controle mudou para {n}, mas as cinco "
                f"lâmpadas não.")
        return ""

    recado = ""
    for alvo, numero in _pares_da_troca(ctx, uniq, n):
        bits = tuple(player_led_pattern(numero))
        corpo = p.player_leds_set_detalhado(bits, uniq=alvo)
        if corpo is None:
            raise RuntimeError(sem_resposta_do_daemon())
        recado = _cobrar_a_frase_do_desenho(ctx, alvo, bits, corpo) or recado
    return recado


def _o_recado(frase: str) -> dict[str, Any] | None:
    """A porta do canal verde: `{"recado": …}` quando há frase, `None` quando não.

    UMA SÓ para os quatro gestos de desenho (`luzes`, `desenho-de`,
    `reenviar-desenho` e `player`), e a razão é a regra desta casa de 05/09:
    *quando a cura conhece a causa, ela cobre TODOS os chamadores*. Quatro
    `if frase:` copiados divergiriam no primeiro ajuste, e o primeiro a divergir
    seria justamente o gesto em que ninguém repara.

    `None` é o silêncio de sempre — e ele não é ausência de resposta: sem frase
    quem responde é a piscada de 1,5 s do piloto
    (`hefesto_vivo.MS_DA_PISCADA`), que é o que a `03-Q4` dela decidiu para o
    desfecho que não tem o que dizer.
    """
    return {"recado": frase} if frase else None


def _o_aviso_dos_n(janela: Any) -> str:
    """A frase do dono para o clique que foi para N controles — "" se N < 2.

    **NENHUMA SÍLABA NASCE AQUI.** O texto é
    `lightbar_actions._AVISO_MESMO_DESENHO_NOS_QUATRO`, o dono único desde a
    L12 (25/08/2026), e a conta é `_quantos_recebem_o_desenho`, o dono único da
    conta. Esta função só junta os dois — que é exatamente o que o
    `_msg_do_desenho` já faz no fim dele.

    **E POR QUE ELA COMPÕE DE NOVO, se a frase do dono já vem com o aviso
    colado:** ela não é o texto que vai à tela — o que vai à tela é a frase
    inteira do dono. Ela é a SONDA que responde *"este desfecho carrega o aviso
    dos N?"*, e é a única pergunta que separa um recibo de um aviso. Sem ela o
    pacote teria de decidir pela conta sozinho, e no dia em que o dono parasse
    de colar o aviso o canal verde receberia um recibo comum — uma frase de seis
    segundos no lugar que existe para contar que o clique pegou em mais de um
    controle. `_cobrar_a_frase_do_desenho` confere que a sonda está DENTRO da
    frase antes de devolvê-la, e é essa conferência que faz as duas metades
    andarem juntas.
    """
    quantos = int(janela._quantos_recebem_o_desenho())
    if quantos < 2:
        return ""
    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        _AVISO_MESMO_DESENHO_NOS_QUATRO,
    )

    return str(_AVISO_MESMO_DESENHO_NOS_QUATRO.format(n=quantos))


def _cobrar_a_frase_do_desenho(ctx: Contexto, uniq: str,
                               bits: tuple[bool, ...], corpo: Any) -> str:
    """Levanta com a frase da GTK quando o desenho NÃO foi para o aparelho.

    NADA DE TEXTO NASCE DESTE LADO, e é o mesmo contrato de `_escrever_a_cor`:
    quem compõe é `lightbar_actions._msg_do_desenho`, o dono ÚNICO da frase do
    desenho das cinco luzes desde a MESA-CHEIA-09/E3 — três caminhos da janela
    GTK passam por ele. Ele é chamado DESLIGADO da instância, com o mesmo
    `_Janela` que a frase da cor já usa: o método lê o estado por funções de
    `app/textos_de_aplicacao` que interrogam um objeto qualquer por `getattr`,
    e o único degrau que ele pede a mais é o `_quantos_recebem_o_desenho` — ver
    lá por que ele é zero nesta aba.

    OS TRÊS ARGUMENTOS DE TEXTO SÃO OS DO GÊMEO — `descricao` de  # (argumento) noqa-acento
    `_descreve_player_leds`, `feito="atualizado"`, `fazer="atualizar"`. É o
    que a GTK passa em `_set_player_leds`, que é para onde vão os botões
    "Desenho do PN" dela; passar outra coisa faria as duas telas do mesmo
    produto contarem o mesmo evento com palavras diferentes.

    **A FRASE FELIZ É PERGUNTADA, NUNCA DIGITADA**, e essa é a diferença para o
    `_escrever_a_cor`: lá o par `(assunto, frase feliz)` existe como constante
    na GTK e se lê de lá; aqui ele é montado DENTRO do `_msg_do_desenho` e não
    tem nome público. Digitá-lo deste lado seria a segunda escrita da mesma
    frase — o defeito que a RADAR-01 mediu. Então pergunta-se ao dono: o MESMO
    método, com um corpo sinteticamente feliz (`aplicado_em` com um destino),
    devolve exatamente o que ele diria se tudo tivesse dado certo. Comparar
    contra isso é perguntar *"a frase que saiu é a do caminho feliz?"* sem
    conhecer uma sílaba dela.

    O CORPO SINTÉTICO NÃO É UM DUBLÊ DO DAEMON: ele nunca vai ao aparelho e
    nunca é lido como resposta. É a pergunta *"o que você diria no melhor
    caso, para este controle, com este desenho?"* — e as duas chamadas usam o
    MESMO `_Janela`, então toda pendência do estado (Modo Nativo, alvo fora da
    mesa) vale igual nas duas e não some na comparação.

    ESTE CAMINHO SÓ CORRE COM O CO-OP FORA. Com ele ligado, `_acender_o_numero`
    volta antes — e é bom que volte: o ramo do co-op no `_msg_do_desenho`
    responde a mesma frase para os dois corpos, e a comparação ficaria cega.

    **E ELE DEVOLVE A FRASE QUANDO ELA TEM AVISO — ILUMINACAO-O-AVISO-DOS-N-01.**
    A comparação acima é surda para o aviso dos N *por construção*: o
    `_msg_do_desenho` cola `_AVISO_MESMO_DESENHO_NOS_QUATRO` no fim de **toda**
    frase que ele compõe quando N ≥ 2 — na do corpo real e na do corpo feliz,
    porque as duas saem do mesmo método com a mesma `_Janela`. As duas ficam
    iguais, o `!=` cala, e o aviso morria aqui dentro: o clique teria pegado em
    N controles e a tela não diria nada. É o defeito que a L12 nomeou —
    *"nada na tela avisava"* — reaparecendo do lado HTML, um degrau adiante.

    Então o desfecho FELIZ deixa de ser mudo: quem tem aviso devolve a frase
    inteira do dono, e o chamador a manda na carga como `{"recado": …}`. Desde
    13/09/2026 essa frase vai ao diário da janela e não à tela (TELA-CALADA-01;
    o relógio verde de 6,0 s que esta nota citava saiu com o canal, na
    FRASES-E-DICAS-01). Sem aviso a devolução é `""` — o silêncio de antes, e a
    piscada continua sendo quem responde.

    :return: a frase do dono quando ela carrega o aviso dos N; `""` quando não.
    """
    dono = _o_dono_da_frase()
    janela = _janela_do_desfecho(ctx, uniq, _nome_da_coluna(ctx, uniq))
    descricao = dono._descreve_player_leds(bits)

    def diz(qual: Any) -> str:
        return str(dono._msg_do_desenho(
            janela, ok=True, motivo=None, corpo=qual, descricao=descricao,
            feito="atualizado", fazer="atualizar"))

    feliz = diz({"status": "ok", "aplicado_em": [uniq], "guardado_em": []})
    frase = diz(corpo)
    if frase != feliz:
        raise RuntimeError(frase)
    aviso = _o_aviso_dos_n(janela)
    if not aviso:
        return ""
    if aviso not in frase:
        raise RuntimeError(
            f"o número mudou em {janela._quantos_recebem_o_desenho()} "
            f"controles.")
    return frase


@gesto("04-iluminacao.html", "player")
def player(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Dar o Player N a este controle" — o número E as cinco lâmpadas.

    NÃO é `identity.renumber`, e a diferença está escrita no
    `interface/pacotes/a01_jogar.py:2427`: o `renumber` COMPACTA todos preservando a ordem
    relativa, e mora na aba Início. Dizer "este controle é o 2" foi o comando
    que faltou ao projeto até 25/07.

    A FUNÇÃO DEVOLVE `(ok, motivo)`, e o motivo já vem traduzido em frase
    (`_MOTIVOS_NUMERO`). Levantar com ele é o que faz o botão RECUSAR em vez de
    falhar calado: desde 13/09/2026 (FRASES-E-DICAS-01) o botão pisca a recusa e
    a frase vai ao diário da janela, sem chegar à tela.

    **ELE ERA MEIO GESTO ATÉ 04/09/2026**, e a metade que faltava é a que ela
    olha: `identity.number.set` troca o NÚMERO EXIBIDO, e as cinco lâmpadas do
    controle não vêm com ele. Ver `_acender_o_numero` para o que foi medido na
    mesa dela — inclusive a razão de a cura óbvia (escrever o desenho por
    `uniq`) não funcionar com o co-op ligado.

    :return: `{"recado": …}` quando o desenho pegou em N > 1 controles
        (ILUMINACAO-O-AVISO-DOS-N-01); `None` no resto. **A troca escrever em
        DOIS controles não é esse caso** — cada um recebe o desenho do NÚMERO
        dele, e o aviso do dono fala de um MESMO desenho.
    """
    uniq = _uniq(o)
    try:
        n = int(str(o.get("player") or "0"))
    except ValueError:
        n = 0
    if not uniq or not 1 <= n <= 4:
        raise ValueError(f"player: preciso do controle e de um número 1..4 (veio {n})")
    ok, motivo = p.identity_number_set(uniq, n)
    if not ok:
        raise RuntimeError(motivo or "não consegui trocar o número")
    return _o_recado(_acender_o_numero(ctx, p, uniq, n))


# ELA DISPENSOU O CAMINHO no dia seguinte, olhando a aba com os quatro DualSense


# `lightbar_brightness` de TODOS os overrides por controle e religava


#: A PORTA DA COR É A `_detalhado` DESDE 03/09/2026, e `led_set` saiu daqui: o
PONTE = {"led_set_detalhado", "identity_number_set",
         "player_leds_set_detalhado", "player_led_brightness_set_detalhado",
         "chamar", "profile_switch"}
METODOS = {"coop.sync"}


PAGINA = "04-iluminacao.html"
#: (o interruptor da D-13) e o `reenviar` (a caixa do hexadecimal).
#: o indicador virou o botão de reenvio (`reenviar-desenho`) e a faixa do título
#: `luzes`, `desenho-de` e `reenviar-desenho` —, e saíram com o widget que os
PISO_DA_ABA = 7
PROVAS = [
    {"pagina": PAGINA, "gesto": "cor", "clique": {"hex": "#FF8000"},  # (noqa-acento) id
     "chama": [("led_set_detalhado", [(255, 128, 0)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "apagar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("led_set_detalhado", [(0, 0, 0)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "reenviar", "clique": {"texto": "#12AB34"},  # (noqa-acento) id
     "chama": [("led_set_detalhado", [(18, 171, 52)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "player", "clique": {"player": "2"},  # (noqa-acento) id
     "chama": [("identity_number_set", ["aa:bb:cc:00:00:01", 2], {}),
               ("player_leds_set_detalhado", [(False, True, False, True, False)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    # Ele provava o `reenviar-desenho`, que era o clique na moldura das cinco
]
