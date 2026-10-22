#!/usr/bin/env python3
"""O pacote da aba `04` Iluminação — a que MAIS tem dono das dez.

O que o daemon devolve (medido em 01/09/2026, DualSense no cabo), tudo com dono:

    lightbar_rgb       [0, 0, 255]   a cor ACESA agora (PÓS-escala de brilho)
    lightbar_on        bool          a barra está acesa
    lightbar_source    str           quem pediu a cor
    lightbar_disputada bool          a Steam abriu o controle
    player             1             o número, das cinco lâmpadas
    leds.lightbar_brightness         o brilho, DO PERFIL (`LedsConfig`, `ge=0.0, le=1.0`)

E desde 25/09/2026 (A-04-PERGUNTA-AO-DAEMON-VIVO-01) o `state_full` publica o brilho que o merge
acendeu:

    brilho_da_barra    0.0-1.0       (lido como `brilho_aceso`)
    brilho_das_luzes   "fraco"…      (lido como `brilho_das_luzes_acesas`)

Quando o vivo e o disco discordam, manda o vivo; o perfil em disco é só a queda quando o daemon não
diz.

**`lightbar_rgb` é PÓS-escala de brilho** (03/09/2026; contrato do daemon, "Contrato de cor (D8)" em
`ipc_handlers._enrich_controllers_per_controller`: `_DesiredOutput.led` já é pós-escala). Lê-lo como
PRÉ-escala mostrava, com brilho abaixo de 100%, uma cor que ela nunca pediu, apagava a marca dos
oito tons e escurecia a tira duas vezes. Quem separa as escalas é `cor_escolhida` (lá a medição, e
por que a inversão é uma varredura, não uma divisão).

Publicação: o `.players` e o trilho (`data-hef-alvo="largura"`) já estão no HTML publicado
(02/09/2026, `6f289554`). Falta UM par, o `.aceso`: a bancada diz `data-campo="luz"
data-hef-alvo="html"`, o publicado ainda `data-campo="aceso"` (ver `desenho_da_luz`).

**`players` e `brilho-pct` NÃO são endereço morto**, embora a régua do mockup diga (02/09/2026, dois
controles, foto lida): a fileira É pintada e a largura É escrita. O defeito é da régua, da família
que `_declarado_neste_elemento` documenta para `classe` e `cor`: entre o emitido e o mostrado há
tradução (`el.style.width = t + '%'` compara `100` com `'100%'`; o alvo `html` cai no ramo padrão e
lê `textContent`, `'1 2 3 4'`). RELATADO; a cura é de `interface/regua_do_mockup.py` e
`interface/hefesto_vivo.py`. Emitir `"100%"` daqui poria `width:100%%` na tela.

Dois endereços mortos morreram aqui (02/09/2026):

    recado   emitido num `data-campo="recado"` que nenhuma das páginas tem (só o `casamento.py` o
    acusava). A frase viaja no `title` das três peças de `luz`, dentro da `dica_da_luz`. rgb
    uma LISTA, e o pintor pula lista em coluna (`hefesto_vivo.py`) e o `casamento.py` também a
    ignora. O `hex` leva a mesma cor na forma que a tela mostra.

**`lightbar_disputada` é o valor mais importante da aba:** com a Steam de posse do controle a cor
publicada é a **pedida**, não a **acesa**. Pintar o hex sem dizer isso afirma uma cor que pode não
estar no plástico.
"""
from __future__ import annotations

import contextlib
import re
from typing import Any

from hefesto_dualsense4unix.interface.monta import (
    MODO_AUTOMATICO,
    MODO_PERSONALIZADO,
    partes_do_modelo,
)
from hefesto_dualsense4unix.profiles.schema import BASES_SEM_COR_DA_LUZ

from . import LUGAR_VAZIO, TRAVESSAO, Contexto, perfil, registrar
from .meus_efeitos import TETO_DO_NOME, guardar_meus_efeitos, meus_efeitos
from .nome_do_jogador import nomes_dos_donos, o_nome_de

SEM_DONO: dict[str, str] = {}


def _hex(rgb: Any) -> str:
    """`(0, 0, 255)` → `#0000FF`, e `—` quando não há cor.

    O travessão é a marca de "não há valor" dos lugares vazios das seis abas; `#000000` diria PRETO,
    que é uma cor. Só formata: a validação de canais é de `cor_do_swatch`
    (`interface/cartao_do_controle.py`), o dono, que recusa lista de quatro canais e grampeia
    0..255.
    """
    if not rgb:
        return "—"
    return "#{:02X}{:02X}{:02X}".format(*rgb)


NUMEROS = (1, 2, 3, 4)

ANEL_DO_DONO = "players.dono"

#: O alvo da cor do plástico (desde 03/09/2026): `escrever()` faz
#: `el.style.setProperty('--plastico', …)`.
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

    O `""` é metade da regra: campo sem informação não mostra nada. O alvo `atributo` APAGA o
    `data-colorway` num valor vazio e o desenho cai nos `fill` crus do `ds_limpo.svg` (um DualSense
    sem identidade, o honesto quando a cor não se lê naquele transporte). Deixar o atributo manteria
    o colorway do MOCKUP sobre um aparelho que é outro. Sem tabela nova: `mesa_viva.CORES` já
    traduziu o código de fábrica do broker para o slug do desenho, e a mesa o carrega em `cor`.
    """
    return str(casa.get("cor") or "")
#: Anel do dono sem cor: `.players .dono{…border:2px solid var(--plastico)}` precisa de
#: `--plastico`; sem ele, tracejado.
ANEL_INCERTO = "border:2px dashed var(--comment)"


def _tinta(rgb: Any) -> str:
    """A cor da tira NO TOM DESTA JANELA — ou `""`, que quer dizer APAGADA.

    Duas escalas da mesma cor: `#0000FF` vai ao plástico; `#7EB8D4` é o azul que esta janela desenha
    (a paleta da casa não tem azul puro). `monta.tom_da_casa` é o dono da tradução, o MESMO que
    pinta a guia de oito botões; o hex CRU poria na tira uma cor que a guia não mostra. O `""` não é
    "sem estilo": manda `desenho_da_luz` desenhar a tira APAGADA, com estilo explícito.
    """
    if not rgb:
        return ""
    import monta

    return str(monta.tom_da_casa(_hex(rgb)))


def chave_do_override(uniq: str) -> str:
    """O `uniq` na forma em que o DISCO guarda a chave de `controllers`.

    Um dono para o endereço do controle no perfil: o `norm_mac` do backend, o MESMO de
    `profiles/schema._validate_controllers_keys`. Escrever `d4:2f:…` onde o disco guarda `d42f…`
    criaria um segundo dono do mesmo controle. Existe desde 03/09/2026, porque o trilho passou a
    ESCREVER; ler numa forma e gravar noutra deixaria o brilho gravado no `aabbcc000001` e a coluna
    lendo o global, para sempre. `""` volta `""`: quem decide sem alvo é o chamador (`_uniq`, que
    recusa dizendo); inventar chave gravaria no controle errado.
    """
    if not uniq:
        return ""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(uniq) or uniq


def brilho_do_controle(p: dict[str, Any] | None, uniq: str) -> float | None:
    """O brilho da barra DAQUELE controle: o override, ou o do perfil.

    Um dono, três chamadores (saiu do `pacote()` em 03/09/2026): a pintura e os gestos que ESCREVEM
    a cor (ver `_escrever_a_cor`); uma segunda leitura do par de campos faria a coluna mostrar um
    número e o fio levar outro. A ordem é a do merge: `ControllerOverrides.leds` vence o
    `LedsConfig` global (`profiles/schema.py`). Aqui só se lê o disco; as cinco camadas quem resolve
    é o daemon.

    `None` = "não sei", não 1.0: a tela mostra `—` e o `led.set` recebe `brightness=None`, que o
    `_payload_led_set` OMITE (o daemon assume 1.0, o retrocompatível). Mandar `1.0` diria "escolheu
    cheio" onde ninguém escolheu.
    """
    if not isinstance(p, dict):
        return None
    leds = p.get("leds")
    global_ = leds.get("lightbar_brightness") if isinstance(leds, dict) else None
    #: Bancada: o `state_full` publica `uniq='143a9a0000ab'`, já normalizado.
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

    A-04-PERGUNTA-AO-DAEMON-VIVO-01 (25/09/2026). Antes o trilho, a caixa `#RRGGBB`, a marca da
    fileira e os gestos liam o DISCO do perfil ativo (`brilho_do_controle`), mas a camada da usuária
    (R-20) atravessa o autoswitch: medido na mesa de quatro, o P1 solto a 60% seguia a 60% depois da
    troca para um perfil de 82%, e o trilho dizia 82%. O dono é `c["brilho_da_barra"]`
    (`ipc_handlers._brilhos_acesos`); sem ele (daemon de outra versão, cor sem brilho, perfil que
    não o publicou), o disco. Não se inventa.

    :param c: a entrada do daemon deste controle (`ctx.por_uniq`), ou `None`.
    :param p: o perfil ativo, CRU (`perfil.ativo`).
    """
    vivo = (c or {}).get("brilho_da_barra")
    if isinstance(vivo, (int, float)) and not isinstance(vivo, bool):
        return max(0.0, min(1.0, float(vivo)))
    return brilho_do_controle(p, uniq)


#: O GESTO DO PAR DOS MODOS (A-O-MODO-AUTOMATICO-E-O-PERSONALIZADO-01, 08/10/2026), no lugar do
#: interruptor `auto-cores` (D-13): automático = interruptor ligado; personalizado = desligado
#: com a cor de cada controle guardada. É também o endereço do quadro, que carrega o modo no
#: `data-modo-da-aba`.
GESTO_DO_MODO = "modo-da-luz"


def automatico_do_perfil(p: dict[str, Any] | None) -> bool:
    """O `leds.auto_player_colors` do perfil ativo: a paleta automática vale quando ligado."""
    if not isinstance(p, dict):
        return True
    leds = p.get("leds")
    if not isinstance(leds, dict) or "auto_player_colors" not in leds:
        return True
    return bool(leds.get("auto_player_colors"))


def _tem_cor_propria(p: dict[str, Any]) -> bool:
    """Algum controle do perfil guarda uma cor escolhida (não preta)?

    Só a de controle conta: no merge do backend a paleta automática vence a cor GLOBAL (`base =
    merge(default, auto)`) e só perde para a do próprio controle (o override). A global num perfil
    com as cores automáticas ligadas não muda o plástico, e a tela não pode dizer Personalizado
    sobre um aparelho no Automático.
    """
    from hefesto_dualsense4unix.core.led_control import cor_escolhida as a_cor_nao_e_o_preto

    def _vale(leds: Any) -> bool:
        rgb = leds.get("lightbar") if isinstance(leds, dict) else None
        if not rgb or len(tuple(rgb)) < 3:
            return False
        r, g, b = tuple(rgb)[:3]
        return a_cor_nao_e_o_preto((int(r), int(g), int(b))) is not None

    return any(_vale((dono or {}).get("leds"))
               for dono in (p.get("controllers") or {}).values() if isinstance(dono, dict))


def modo_da_luz_do_perfil(p: dict[str, Any] | None) -> str:
    """O modo da aba (Automático ou Personalizado), lido do perfil CRU.

    A regra é a do esquema (`decidir_o_modo_da_luz`), a mesma do `ProfileManager`: tela e plástico
    não discordam. Sem perfil, Personalizado: a vista do computador (`perfil.ativo_que_vale`, sem
    `name`) só diz Automático se ele está escrito; deduzir dela pintava Automático no primeiro
    efeito.
    """
    from hefesto_dualsense4unix.profiles.schema import decidir_o_modo_da_luz

    if not isinstance(p, dict) or not p:
        return MODO_PERSONALIZADO
    leds = p.get("leds")
    escrito = leds.get("modo") if isinstance(leds, dict) else None
    if "name" not in p:
        return MODO_AUTOMATICO if escrito == MODO_AUTOMATICO else MODO_PERSONALIZADO
    return decidir_o_modo_da_luz(
        escrito if isinstance(escrito, str) else None,
        automatico_do_perfil(p), _tem_cor_propria(p))


def _o_modo_escrito_e_automatico(p: dict[str, Any] | None) -> bool:
    """O perfil traz o modo automático ESCRITO em `leds.modo` (e não deduzido)?"""
    leds = p.get("leds") if isinstance(p, dict) else None
    return isinstance(leds, dict) and leds.get("modo") == MODO_AUTOMATICO


RECADO_DO_AUTOMATICO_PARADO = (
    "A iluminação está no modo automático: cada controle acende a cor do plástico dele. "
    "Passe para o modo personalizado para escolher.")


def _nao_no_automatico(ctx: Contexto) -> None:
    """A guarda de cada gesto que escolhe a luz de um controle (ver `_recusar_no_automatico`)."""
    nome = perfil.nome_do_ativo(ctx.state).strip()
    _recusar_no_automatico(perfil.ativo_que_vale(nome))


def _recusar_no_automatico(cru: dict[str, Any] | None) -> None:
    """A recusa dos gestos de cor, brilho e números quando o Automático está ESCRITO.

    A tela já deixa a coluna parada, então o clique não chega; esta é a porta de quem fala com o
    gesto sem a tela. Só o modo escrito recusa: o perfil sem `leds.modo` segue aceitando o que
    sempre aceitou.
    """
    if _o_modo_escrito_e_automatico(cru):
        raise RuntimeError(RECADO_DO_AUTOMATICO_PARADO)


ROTULO_DO_BRILHO = "Brilho da barra de luz deste controle"

DICA_DO_BRILHO = ("Brilho da barra deste controle. Grava no perfil ao "
                  "soltar — não espera o Salvar perfil.")


def _com_o_brilho(rgb: tuple[int, int, int], brilho: float) -> tuple[int, int, int]:
    """`rgb` escalado pelo brilho — **pela função do produto**, nunca por conta.

    O dono é `core/led_control.LedSettings.apply_brightness`, que passa pelo PISO
    (`fator_do_brilho`, D-2909-O-BRILHO-TEM-PISO); o `_handle_led_set` e o provider da cor
    automática (D11) chamam o mesmo, e por ser a mesma conta a varredura de `cor_escolhida` é exata.
    """
    from hefesto_dualsense4unix.core.led_control import LedSettings

    return LedSettings(lightbar=rgb).apply_brightness(brilho).lightbar


#: Fora da guia: os três de 11/09 (um azul, um rosa e o preto) e, desde 14/10/2026, mais dois (verde
#: limão e verde água): a fileira do desenho do todo é a das cores de jogador,
#: `player_slot_color(1..8)`, com o branco na frente e sem :data:`SAI_DA_GUIA`.
FORA_DA_GUIA = ("#0080FF", "#FF00FF", "#000000", "#80FF00", "#00FF80")

#: A primeira casa da guia é o branco (19/10/2026), e o ciano do Player 6 sai: eram dois azuis na
#: fileira. O Player 6 nunca acende sozinho (a mesa é de quatro); a cor automática dele segue no
#: daemon. Os Players 1 a 4 continuam com casa, e por isso o azul que fica é o do Player 1.
PRIMEIRA_CASA = (255, 255, 255)
SAI_DA_GUIA = 6


def tons_da_guia() -> tuple[tuple[int, int, int], ...]:
    """Os tons que a guia desta aba oferece, na ordem do desenho: o branco e as cores de jogador.

    Nenhum se digita: os OITO são `core/led_control.player_slot_color(1..8)` (a paleta das cinco
    lâmpadas e a cor automática de cada número, o atalho para a cor do jogador); sobram as chaves de
    `monta.TOM_DA_CASA` que os oito não cobrem e :data:`FORA_DA_GUIA` não tirou (hoje nenhuma).
    Eram oito até 09/09/2026, catorze até 11/09 e onze até 14/10 (decisão de produto; a poda é de
    espaço).

    Quem filtra é esta função, não o dono dos tons: `TOM_DA_CASA` segue com os catorze e
    `player_slot_color` com os oito (os dois em `nao_toca` da sprint: a cor automática do jogador é
    do daemon). Recusa dizendo, porque um erro em :data:`FORA_DA_GUIA` seria mudo:

    1. um hex que não está em `TOM_DA_CASA` não tira nada (linha morta parecendo decisão);
    2. um hex que é cor automática de jogador quebraria `titulo_da_casa`, que promete *"Cor
    automática do Player i"* às oito primeiras casas pela POSIÇÃO.

    A ordem importa: quem procura a cor do próprio número a acha onde sempre esteve; o novo entra
    depois.
    """
    import monta

    from hefesto_dualsense4unix.core.led_control import player_slot_color

    automaticos = tuple(player_slot_color(n) for n in range(1, 9))
    guia = (PRIMEIRA_CASA, *(t for n, t in enumerate(automaticos, start=1) if n != SAI_DA_GUIA))
    ja_tem = {"#{:02X}{:02X}{:02X}".format(*rgb) for rgb in (*automaticos, PRIMEIRA_CASA)}
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
    return guia + extras


def titulo_da_casa(i: int) -> str:
    """A frase de cada casa da guia: o branco, e depois a cor de cada número, pelo tom da casa."""
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    tons = tons_da_guia()
    tom = tons[i - 1] if 0 < i <= len(tons) else None
    numero = next((n for n in range(1, 9) if tuple(player_slot_color(n)) == tom), None)
    quem = "Branco. " if tom == PRIMEIRA_CASA else f"Cor do Player {numero}. " if numero else ""
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


def _as_luzes_do_plastico() -> frozenset[tuple[int, int, int]]:
    """Os tons de luz que a tabela do plástico dá: a cor automática de cada casco."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import TABELA, tom_da_luz

    luzes = (tom_da_luz(cor) for cor in TABELA.values())
    return frozenset(luz for luz in luzes if luz is not None)


def a_casa_da_cor(rgb: Any) -> str | None:
    """A CASA da guia de uma cor pedida: o tom que a acende, ou o mais perto.

    A escada: o tom exato; o mesmo tom em outro brilho (se for UM só); e, sem nenhum dos dois,
    quando a cor é **a luz de algum plástico**, o tom da guia mais perto no RGB (empate, o
    primeiro). O último degrau existe porque a cor automática é o tom do plástico (`tom_da_luz`,
    D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO), que cai fora dos onze (Cosmic Red `(255, 0, 82)`,
    Starlight Blue `(0, 172, 255)`): a barra acende a cor do plástico e só a fileira marca o tom
    vizinho.

    Sem casa: o preto; a cor acesa IGUAL por mais de um tom (0,4% a 0,7% de brilho: escolher seria
    escolher por ela); e a cor posta fora da guia que não é luz de plástico (o global `#2850B4`,
    A-PALETA-MARCA-A-COR-DE-CADA-CONTROLE-01): marcar o vizinho inventaria um dono.
    """
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
    if casados:
        return _hex(casados[0]) if len(casados) == 1 else None
    if alvo not in _as_luzes_do_plastico():
        return None
    return _hex(min(tons, key=lambda t: sum((a - b) ** 2
                                            for a, b in zip(t, alvo, strict=True))))


def a_chave_da_cor(rgb: Any) -> str | None:
    """Onde a cor pousa na mesa das casas: a casa, ou a própria cor sem casa."""
    if not rgb or len(tuple(rgb)) < 3 or tuple(rgb)[:3] == (0, 0, 0):
        return None
    return a_casa_da_cor(rgb) or _hex(tuple(int(c) for c in tuple(rgb)[:3]))


def as_casas_da_mesa(pecas: Any) -> dict[str, list[dict[str, Any]]]:
    """A MESA DAS CASAS: `{casa: [donos na ordem do número]}`, uma vez por tique.

    Uma mesa para as três perguntas (o X, a marca própria e a recusa); duas peças no mesmo tom (o
    «Todos», ou o global de vários) ficam as duas na casa. A entrada é dado puro, uma peça por
    controle (`quem`, `cor`, `nome`, `numero`, `plastico`), para o pacote e a bancada chamarem a
    mesma função (`quem` = `uniq` no produto, o lugar na bancada).
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

    Dois chamadores: o pacote (`_as_pecas_da_mesa`) e a bancada do `aba04.py`. É o casco por
    `cor_de_css` (`_cor_do_plastico`) passado pelo piso de contraste do card (`tom_para_a_borda`),
    como a borda da 02: a linha mora no painel escuro e o Midnight Black cru sumiria.
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
    """Os tons de uma coluna (as oito cores de jogador), em HTML — o miolo da `.guia`.

    COR-X-01 (09/09/2026): *"onde eu escolher uma cor, em volta dela fica a borda da cor do plastico
    do controle e um X na cor selecionada por mim de forma que me impeça de setar alguma cor de um
    coleguinha"*
    <!-- noqa-acento: citação literal -->

    D-2909-A-LINHA-DA-COR-DO-DONO (29/09/2026): toda casa com dono ganha embaixo a linha do plástico
    de quem a usa, nas quatro colunas (`--dono`, ver `tinta_da_linha`). A borda da escolhida saiu:
    era a cor de texto do `<button>` (quase preta) e sumia no Starlight Blue sobre a casa azul e no
    White sobre a casa branca. Pedido: *«talvez uma linha abaixo do quadradinho de cada cor contendo
    a cor do
    plástico daquele controle»* <!-- noqa-acento: citação literal -->

    A fileira inteira, não um endereço por botão (como `fileira_de_players`): o alvo `classe` do
    pintor compara por IGUALDADE (`hefesto_vivo.escrever`, `aceso = (t === quando)`), e "esta cor
    está entre as que os OUTROS tomaram" não é igualdade. Quem vê a mesa inteira é o pacote.

    Cada casa responde «de quem é?» pela mesa das casas (`as_casas_da_mesa`;
    A-PALETA-MARCA-A-COR-DE-CADA-CONTROLE-01):

    * `on` quando a casa tem este controle; * X quando a casa tem outro dono e não tem este (preto
    com contorno branco, porque a cor do plástico sumia no tom pastel); no «Todos» a casa de todos
    não ganha X em coluna nenhuma;
    * `data-gesto` só onde a recusa passa: a casa sem dono e a casa só dele. A que ele divide com
      outros (o «Todos», o global num tom) fica `on`, sem X nem gesto, com `aria-disabled` (o clique
      piscava a recusa); * a `data-dica` da casa com dono alheio nomeia os donos (um X mudo obriga a
      adivinhar); * a linha: toda casa com dono, a dele também; a casa dele é a que tem a linha da
      cor da moldura e não tem X.

    :param meu: quem é esta coluna (`uniq` no produto, o lugar na bancada).
    :param casas: a mesa das casas (`as_casas_da_mesa`), com este controle.
    :param ligado: há controle neste lugar? Lugar vazio não ganha `on` nem X.
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
        aberto = ("" if outros else f' data-gesto="cor" data-hex="{cru}"')
        travado = ' aria-disabled="true"' if outros else ""
        linhas.append(
            f'{recuo}<button class="{classes}" style="{estilo}"'
            f'{aberto}{travado} data-dica="{titulo}"></button>')
    return "\n".join(linhas)


def cor_escolhida(efetiva: Any, brilho: float | None) -> Any:
    """A cor que o usuário PEDIU, a partir da que está ACESA e do brilho.

    O `lightbar_rgb` do daemon é PÓS-escala de brilho (contrato D8,
    `ipc_handlers._enrich_controllers_per_controller`: o `_DesiredOutput.led` já é pós-escala). Lido
    como ESCOLHIDA, com brilho abaixo de 100% quebrava três coisas (medido em 03/09/2026,
    `brilho=0.5`, azul do P1):

        a caixa `#RRGGBB`   dizia `#00007F`, cor que ela nunca pediu
        a marca dos 8 tons  apagava em todos (`data-hef-quando` compara com `#0000FF`)
        a tira              pintava o hex CRU e ainda aplicava `opacity:0.5`: o brilho
                            escurecia DUAS vezes

    A cura é a INVERSÃO pela fórmula do produto, não uma divisão (`127/0.5` dá 254 e a marca
    seguiria apagada por um): aplica-se a conta do dono (`_com_o_brilho`) aos tons e vê-se qual
    produz a cor acesa, como `lightbar_actions.nome_do_desenho` faz com os oito padrões.

    A varredura é de `monta.TOM_DA_CASA`, OS CATORZE, não os onze da guia: inverte *o que o produto
    pode ter ACESO*, não *o que a guia oferece hoje*. Um perfil salvo no `#0080FF` a 50% acende
    `#004080`; varrer só os onze devolveria o escuro e a caixa mostraria uma cor nunca pedida por
    causa de uma poda de tela (:data:`FORA_DA_GUIA`, 11/09/2026).

    Sem casamento a efetiva volta inteira (cor que não é tom da casa, como o global `#2850B4`, que a
    82% acende outro hexa): mostra-se o que está no plástico; inventar um pedido seria afirmar
    escolha que ninguém fez.

    O preto não casa e o casamento tem de ser ÚNICO (A-MARCA-DA-COR-NAO-SOME-01, 24/09/2026):
    devolver o PRIMEIRO tom que casasse fazia, a 0% (todos acendem `(0, 0, 0)`), a coluna de quem
    apagou pelo trilho dizer azul, o X da cor dele sumir dos outros três e o P1 ganhar X na PRÓPRIA
    cor (medido no piloto, com o clique). Ver `_o_tom_que_acende`.

    :param efetiva: o `lightbar_rgb` do daemon, ou `None`/vazio quando não há.
    :param brilho: `brilho_aceso`. `None` ou `1.0` devolvem a efetiva sem varrer (a 100% as escalas
    são a mesma).
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

    É a varredura de `cor_escolhida` com a conta do dono (`_com_o_brilho`). Devolve `None` em vez da
    efetiva porque o chamador precisa saber se a luz acesa DISSE a cor: é aí que a escada de
    `_a_cor_de_agora` desce um degrau. `None` em três casos (os dois primeiros medidos no piloto,
    com o clique, em 24/09/2026):

    * **nenhum tom casa**: a luz publicada é de OUTRO brilho. O gesto `brilho` grava no disco antes
    de o daemon publicar a luz nova (o `state_full` guarda a leitura do nó por 1 s), e por meio
    segundo cada tique invertia a luz velha com o brilho novo;
    * **a luz está apagada**: a 0% os catorze acendem preto, e acima de 0% o `#000000` é o único que
      acende preto; subindo o trilho a partir de 0% a coluna inteira virava preta por meio segundo.
      Luz apagada não diz cor (o preto é banido como cor, ordem de 22/09 que
      `led_control.cor_escolhida` guarda); a de quem apagou pelo «Desligar» está GRAVADA com brilho
      0%, e o degrau seguinte da escada a devolve;
    * **mais de um tom casa**: de 0,4% a 0,7% o vermelho, o rosa e o laranja acendem `(1, 0, 0)`, e
      há trios iguais no azul e no verde. Devolver o primeiro da tabela seria escolher por ela.

    A 100% (ou sem brilho) não há conta a desfazer: a luz é o tom, se for um dos catorze.
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

    O discriminador é o PRIMEIRO retorno de `interface/cartao_do_controle.rotulo_lightbar`, não o
    segundo: a cor devolvida é a BASE do accent e vem PREENCHIDA no ramo em que o motor avisa que
    ela pode não estar no plástico (a Steam); lê-la como "há luz?" colapsa dois estados (defeito que
    a `a02_controles` mediu em 02/09/2026). Os quatro ramos (`controller_card.rotulo_lightbar`):

        (None, rgb)                        cor conhecida e acesa      → acesa
        "Lightbar: apagada"                fonte NOSSA, desligada     → apagada
        "A Steam tem este controle aberto" quem segura o `fd`         → incerta
        "Lightbar: cor desconhecida"       sem fonte, ou sem rgb      → incerta

    O modo Nativo não é ramo (D-2409-NO-NATIVO-A-TELA-MOSTRA-A-COR): a barra é do Hefesto e a tira
    desenha a cor como em todo modo.

    A frase da apagada não se digita, se PERGUNTA (só `ROTULO_LIGHTBAR_SEGURADA` é constante
    exportada; `a02_controles.ROTULO_DA_LUZ_APAGADA` já faz isto na aba irmã): a entrada mínima que
    só o ramo "apagada" atende. Uma segunda derivação envelheceria calada se o motor trocasse a
    frase, e a aba voltaria a colapsar "apagada" com "não sei".
    """
    from .a02_controles import ROTULO_DA_LUZ_APAGADA

    if recado is None:
        return ACESA
    return APAGADA if recado == ROTULO_DA_LUZ_APAGADA else INCERTA


def o_coop_manda(state: dict[str, Any]) -> bool:
    """O co-op está DE FATO numerando mais de um controle?

    Não se lê `coop.enabled`: `status_actions.texto_do_coop_derrubado` registra que
    `CoopManager.disable()` não zera `coop_enabled`, então o `state_full` segue com
    `coop.enabled=True` e `coop.players=1`, indistinguível de 'ela desligou o co-op' (medido em
    02/09/2026, co-op parado e dois controles: `"coop": {"enabled": true, "players": 1, "mesa": [uma
    entrada]}`).

    Quem manda nas cinco lâmpadas é a CAMADA de co-op do merge
    (`backend_pydualsense._merged_desired_for_key`, a segunda de cinco), que só opina com mais de um
    jogador. Ler o booleano mandaria o `player` pedir um `coop.sync` inútil numa mesa de um jogador
    e deixaria sem escrever o override que acende ali (`_acender_o_numero`). Em 25/09/2026
    (O-CO-OP-LOCAL-SAI-01) o ramo seguiu de pé: o Hefesto publica o número da mesa
    (`CoopManager._apply_coop_player_leds`, só com `players > 1`) e o co-op não é modo que se liga
    (D-2409-O-CO-OP-LOCAL-SAI); esta função responde «há mais de um jogador».
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

    Decisões de 02/09/2026: «a palavra ACESO sai do texto» e «a interface mostra o que tá conectado
    e não o controle do mockup». O desenho trazia `title="O Cosmic Red aceso: as duas tiras na cor
    escolhida, e as cinco lâmpadas no padrão do Player 1."`: o nome era o do mockup (a mesma coluna
    escrevia `P1 • White • USB` no rótulo e `Cosmic Red` na dica), e `aceso` afirma estado do
    aparelho que ninguém confere (a GTK já a tirou em 25/08, `lightbar_actions._PREFIXO_DESENHO`).

    A frase do desenho das 5 luzes saiu junto: *"Desenho que mandamos: desenho do PN — automático"*
    afirma o MERGE do backend (`_merged_desired_for_key`: default global < AUTOMÁTICA < override
    por-uniq < co-op < jogo), e **este pacote não vê o override por-uniq**. O `state_full` publica
    por controle as chaves de `ipc_handlers._enrich_controllers_per_controller` (`lightbar_rgb`,
    `lightbar_on`, `lightbar_source`, `player_slot`, `inputs`…), nenhum do desejado
    (`aba02.py:1388`: publica `player_slot`, NÃO `player_leds`); e o override é onde a GTK escreve
    ao aplicar um desenho (`lightbar_actions._enviar_player_leds` → `player_leds_set_detalhado(…,
    uniq=…)` → `_apply_por_uniq` → `apply_output_for`). Reproduzido em 02/09/2026 com o merge real e
    nenhum aparelho (dublê de `test_troca_de_player_01_a_escolha_sobrepoe.py`): com override
    `[T,F,F,F,T]` a tela dizia "desenho do P2 — automático" e o fio levava `[T,F,F,F,T]`. Regra de
    produto: *"se não tá mostrando agora, não tem info pra mostrar no produto"*.

    O que sobra é o que se mede: a frase da BARRA é o primeiro retorno de
    `controller_card.rotulo_lightbar` (a dos cards da GTK, que sabe os quatro estados em que a cor
    publicada **não** está no plástico). `""` quando não há ressalva.

    A frase do co-op saiu (O-CO-OP-LOCAL-SAI-01, 25/09/2026, D-2409-O-CO-OP-LOCAL-SAI): tratava o
    co-op como modo que se liga, mas o Hefesto dá um controle virtual a cada jogador sempre e numera
    as lâmpadas (D-2309-O-HEFESTO-MANDA-NO-NUMERO); e o que explicava (escolher desenho à mão não
    adianta) perdeu o assunto em 07/09, quando a botoeira saiu. **A dica é a mesma com um jogador ou
    quatro**; régua: `tests/unit/test_o_co_op_local_saiu.py`.

    :param nome: o modelo VIVO, o que a mesa sabe, nunca o do desenho.
    :param via: `USB`/`BT` de agora; `—` ou vazio some da frase (um travessão entre parênteses não
    diz nada). :param recado: o primeiro retorno de `rotulo_lightbar`, ou `""`.
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
    """O número deste controle, pela regra do MOTOR — que tem UM dono.

    `app/actions/base.numero_do_controle` (COR-01/D6): o `player_slot` de sessão, que sobrevive a
    desconectar e reconectar, com queda para a posição (uma cópia por tela dava duas verdades sobre
    qual é o 'Controle 1'). Esta aba tinha a terceira cópia, errada: o rótulo lia só `player`,
    `None` para quem não joga co-op, e escrevia `Modelo: P—` com o botão `2` ACESO logo abaixo (D2,
    02/09/2026); a quarta estava no gesto `auto` (`player_slot or player or 1`). A mesa já chama o
    motor (`mesa_viva.mesa_do_estado` põe `numero_do_controle(entrada)` em `jogador`): ler dela
    concorda com a fita e o cabeçalho; perguntar ao motor é a queda para o controle fora da mesa.
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

    Dois chamadores, um dono: o gerador `aba04.py` (bancada) e o pacote (a cada tique, a fileira
    viva). Duas escritas deixariam o botão do desenho e o do produto divergirem sem ninguém ver.

    O dono só existe se estiver na mesa (31/08/2026): o `title` dizia *"o Galactic Purple, que tem o
    3 hoje"* com ele DESCONECTADO.

    Quatro estados (ver `ANEL_INCERTO`); a tela mostrava dois, e o terceiro caía no primeiro:

        livre            ninguém tem este número                  sem anel
        tomado           a cor do dono é conhecida                anel cheio, na cor do plástico
        tomado, sem cor  o dono está aqui, a cor não chegou       anel TRACEJADO
        fora da mesa     não há controles bastante                apagado, e a dica diz o número

    O quarto nasceu de um clique (03/09/2026, produto instalado, UM controle): a dica dizia "Player
    3 — livre.", o botão era idêntico ao 1 e clicar devolvia `RuntimeError: Esse número é maior do
    que a quantidade de controles ligados`. Com `quantos=1` valia para TRÊS dos quatro botões.

    `quantos` é a MESA, não os donos: o daemon compara o número com **quantos controles estão
    ligados**, e `donos` só tem os com item de mesa; contar `donos` diria "fora da mesa" a um número
    que o produto aceitaria. KEYWORD-ONLY e SEM PADRÃO de propósito: com padrão, quem esquecesse
    voltaria calado a um dos estados acima.
    """
    cor = _cor_do_plastico(str(dono.get("cor") or "")) if dono else ""
    #: O endereço e o alvo andam juntos: endereço sem alvo é meia fechadura.
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
            f'data-gesto="player" data-player="{n}" data-dica="{dica}">{anel}{n}</button>')


def fileira_de_players(nome: str, meu: int, donos: dict[int, dict[str, Any]],
                       recuo: str = "", *, quantos: int) -> str:
    """Os quatro botões de uma coluna, em HTML — o miolo de `.players`.

    A fileira inteira, não um endereço por botão: o que muda é **qual botão fica `on`** e **o texto
    da dica**, e o pintor (`hefesto_vivo.escrever`) escreve texto, largura, fundo, valor e HTML,
    **classe não**. Com um `data-campo` por botão só entraria texto, e texto num `<button>` apaga o
    anel do dono dentro dele. O alvo `html` é o degrau da fita e do mapa do gabinete: bloco cujo
    conteúdo muda com a mesa se troca inteiro (o ouvinte de clique é delegado no documento, trocar o
    HTML não desliga botão). `quantos` atravessa: ver `um_botao_de_player`.
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
            f'data-luzes="{valor}" data-dica="Luzes de número: {rotulo}">{rotulo}</button>')
    return "\n".join(botoes)


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

    A ordem do `brilho_do_controle`: o override por controle vence a seção global, que vence o
    padrão do esquema (`LedsConfig.player_led_brightness`, o Fraco). Aqui só se lê o disco; no
    aparelho quem resolve é o daemon. Sem perfil lido devolve o padrão, não `""`: todo controle
    nasce no Fraco (decisão de produto).
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

    Antes (02/09/2026, dois controles) o pacote escrevia a palavra `Aceso` por um `data-campo` de
    alvo `texto`; `escrever()` faz `el.textContent = t`, que **apaga os filhos**, e as tiras e
    lâmpadas sumiam no primeiro tique (a régua do mockup contava como PRODUTO, porque o valor MUDOU;
    mesma família do `balanceado` dentro dos botões da Vibração e da contagem dentro do `<tbody>` da
    Perfis). A pergunta que vale para toda aba: *isto é um DADO ou é o DESENHO?* Desenho cujo
    conteúdo muda com o dado se troca INTEIRO, pelo alvo `html`, como a fita, o mapa do gabinete e a
    fileira de players.

    Um dono, dois chamadores: o gerador `aba04.py` (bancada) e o pacote (produto, a cada tique).
    Tudo tem dono no motor: as lâmpadas saem de `monta.luzinhas`
    (`core/led_control.player_led_pattern`, o MESMO padrão do daemon); a tinta é `_tinta`; se HÁ cor
    a afirmar quem decide é `controller_card.rotulo_lightbar` (o chamador passa `""` quando não há);
    a `dica` é `dica_da_luz`.

    A dica viaja nas TRÊS peças, não na célula: `title` é atributo e o piloto não tem alvo de
    pintura para atributo (os alvos são `texto`, `largura`, `fundo`, `valor`, `html`, `classe` e
    `cor`), então o da célula ficava CONGELADO (dizia *"O Cosmic Red aceso…"* na coluna de um
    controle branco). Nas peças entra pelo alvo `html` e muda com a mesa. RELATO: um alvo `titulo`
    no piloto curaria as dezenove dicas congeladas desta aba de uma vez.

    :param tinta: o hex JÁ no tom da casa. `""` desenha a tira APAGADA (`TIRA_APAGADA`), nunca uma
    tira sem estilo. Com `estado=INCERTA` não é olhada: quem não sabe não pinta. :param brilho: de
    0.0 a 1.0, a opacidade das duas tiras ACESAS (a apagada não tem brilho). :param jogador: o
    número deste controle, a ÚNICA fonte das cinco lâmpadas desde 07/09/2026: elas espelham a linha
    `Jogador`, e a célula `LEDs` não diverge do número da célula de cima. :param dica: a frase de
    `dica_da_luz`, ou `""` (sem ela as peças saem sem `title`). :param estado: `ACESA`, `APAGADA` ou
    `INCERTA`, o que `estado_da_tira` respondeu. `""` = **sem estado declarado**, e aí a tinta
    decide: é o que a BANCADA sabe, sem motor a perguntar. Nunca vale `INCERTA` por omissão.
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
    try:
        lampadas = monta.luzinhas(jogador)
    except KeyError:
        # O dono (`player_led_pattern`) sabe o overflow e o atalho da bancada não:
        # `monta.luzinhas(9)` levanta `KeyError` (medido em 02/09/2026).
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

    Importa tarde de propósito, como o `import monta` das outras funções: os pacotes das dez abas se
    registram no import, e uma dependência no topo entre dois amarraria a ordem de carga. Um dono,
    dois chamadores (como `fileira_de_players` e `desenho_da_luz`): copiá-la daria duas leituras do
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

    Um dono, dois chamadores (como `fileira_de_players`): o gerador as põe na folha da página (a
    bancada se vê sem daemon); este pacote as põe na folha VIVA, porque a página PUBLICADA ainda não
    as tem. Duas escritas dariam dois brancos na mesma célula. O `--luz-apagada` NÃO entra, a
    mordida decidiu: ver `LUZ_APAGADA`.
    """
    return (f"{ESCOPO_DO_DESENHO}{{"
            f"--led-apagado:{token_das_luzinhas('--led-apagado')};"
            f"--led-aceso:{token_das_luzinhas('--led-aceso')}}}")


def folha_da_luz(luzes: dict[str, tuple[str, int | None]],
                 caixa: str = CAIXA_DA_COLUNA) -> str:
    """A folha viva da LUZ: a barra e as cinco lâmpadas do DESENHO GRANDE.

    Medido no DOM vivo (03/09/2026, UM controle no cabo,
    ``ensaios/a_luz_do_desenho_e_a_luz_do_aparelho.py``): o aparelho dizia (0, 0, 255) e o desenho
    acendia (126, 184, 212), e o número 1 pedia a lâmpada 3 e o desenho não acendia nenhuma. O
    `#7EB8D4` é o `--luz` que o GERADOR crava no `<g>`, a cor do MOCKUP parada sob um hex que já
    dizia `#0000FF`.

    Uma folha, não um campo (como `folha_do_plastico`): o pintor escreve texto, largura, fundo,
    valor, `innerHTML`, classe, cor, atributo e `--plastico`, **nenhum escreve `--luz`**. Reescrever
    o SVG por `innerHTML` custaria as 370 linhas do desenho a cada meio segundo e nunca sossegaria
    (o navegador normaliza a marcação); o `innerHTML` de um `<style>` é TEXTO e volta como foi
    escrito.

    O `!important` é o único caminho: o `--luz` do mockup mora no atributo `style` do `<g>` e
    declaração de linha vence folha; a marca `led-on` é cravada nos `<rect>` que o MOCKUP escolheu e
    só some do cálculo com regra `!important` de igual especificidade. A ORDEM das duas regras de
    lâmpada decide: as cinco apagam primeiro, as do padrão acendem depois (as duas valem (0,3,0) e
    `!important`, o último ganha; na ordem inversa a lâmpada recém-acesa apagaria).

    Sem cor a afirmar, a barra apaga (*"se não tá mostrando agora, não tem info pra mostrar no
    produto"*), nos quatro lugares: um lugar sem controle recebe as regras de apagado, senão o
    `--luz` do mockup fica aceso num lugar que diz "Desconectado".

    :param luzes: por lugar (`p1`…`p4`), o par `(hexadecimal da barra, número)`. Hex vazio ou `—`
    apaga a barra; número `None` apaga as cinco lâmpadas; lugar ausente é tratado como apagado.
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

    Mesmo guarda de `desenho_da_luz`: `monta.PADRAO_JOGADOR` só precomputa 1..8 e
    `monta.luzinhas(9)` levanta `KeyError`, enquanto `core/led_control.player_led_pattern` responde
    a qualquer número (só o gerador chamava, com 1..4).
    """
    import monta

    try:
        return str(monta.luzinhas(int(numero)))
    except (KeyError, TypeError, ValueError):
        return ""


def item_da_troca(nome: str, numero: int, plastico: str,
                  mexeu: bool = False) -> str:
    """Um controle com um número, no antes/depois do rodapé.

    `data-hef` pela mesma razão do anel da fileira: o `--plastico` mora no `style` DESTE elemento e
    a régua da identidade o julga no elemento que o carrega. Aqui ele não é congelado (a seção
    inteira é um `blocos:` que o produto reescreve com a mesa viva), e o endereço diz isso. O alvo
    veio em 03/09/2026 porque só o endereço não bastava: o `blocos:` reescreve o miolo por
    `document.querySelector`, a troca mora no JavaScript e nenhuma régua a vê lendo o HTML. Com
    `data-hef-alvo="plastico"` o pintor escreve a variável no PRÓPRIO item (`cores_da_troca` manda a
    lista, na ordem do documento) e o antes invisível deixa o selo da visita.

    O anel tracejado vale aqui também (03/09/2026, como `ANEL_INCERTO`): todo item é um controle na
    mesa, sem "livre" a confundir; o que havia era o anel SUMINDO, porque sem `--plastico` a folha
    (`border:2px solid var(--plastico)`) fica inválida no cômputo e o `border-style` cai para
    `none`.

    :param plastico: o hex da casca, ou `""`; sem hex o anel é TRACEJADO, como esta aba diz "não
    sei" (decisão 9 dela).
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

    São duas linhas com os mesmos controles (ANTES e DEPOIS) e o que muda é o número, nunca a casca:
    a lista é a mesma sequência duas vezes. Vazia quando não há troca a contar: com menos de dois
    controles a seção não desenha item (`secao_da_troca`), e valor a mais escreveria num item
    inexistente.
    """
    ordenada = _ordem_da_troca(mesa)
    if len(ordenada) < 2:
        return []
    cores = [_cor_do_plastico(str(c.get("cor") or "")) for c in ordenada]
    return cores + cores


def secao_da_troca(mesa: list[dict[str, Any]], recuo: str = "  ") -> str:
    """A seção "Trocar o número" inteira, com a mesa que lhe derem.

    Deixou de ser texto fixo em 03/09/2026 (lei de produto: cada aba usa os controles que o topo
    mostra, nunca os do mockup). Era o caso REAL de 26/08 (o controle azul era o player 2 e
    precisava ser o 1 antes do jogo), escrito com os dois controles do DESENHO num rodapé que o
    produto renderiza. Um dono, dois chamadores: o gerador desenha a bancada e o pacote a manda a
    cada tique por `blocos:`.

    A troca precisa de dois: com menos de dois controles na mesa a seção diz isso em vez de inventar
    um segundo.
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

    Pedido de 21/09/2026, zero controles: *"os leds na linha dos leds do p3,p4 tem que aparecerem
    mas não aparecerem ligados como o p1 e o p2"* (o P1 e o P2 mostravam as duas tiras ACESAS no
    azul e no vermelho do mockup, porque o alvo `html` fica fora do travessão e ninguém repintava; o
    P3 e o P4 um travessão seco).

    * Linha LEDs = o desenho apagado: as duas tiras em `TIRA_APAGADA` e as cinco lâmpadas sem
    nenhuma acesa (`monta.luzinhas(0)`); lugar vazio não tem número, acender o padrão do P1 diria
    um. * Linha Jogador = o travessão (não há número a escolher, e é a palavra que o próprio desenho
    usa ali); antes o P1 e o P2 a deixavam em branco (a folha esconde os botões do lugar esvaziado)
    e o P3 e o P4 escreviam `—`. * O estilo vai NO travessão: a tinta cinza e o centro de
    `.ctrl.vazia[data-conectado="nao"] .nada` não valem para o lugar que ESVAZIOU (não é `.vazia`);
    medido na foto de 21/09 o traço do P1 saía branco e à esquerda do cinza centrado do P3. Regra
    nova na folha seria pixel da página publicada; esta é a mesma, no elemento.
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


#: O EFEITO DA BARRA (A-ABA-ILUMINACAO-DO-TODO-01). A lista da coluna tem «Sem efeito» (a barra
#: apagada), «Luz fixa» (a cor de sempre), as oito bases em grupos pelo que se vê (o desenho A de
#: 15/10/2026, a escolha do usuário: «uma lista suspensa em cada escolha») e os efeitos que a pessoa
#: criou.
#: O valor de um efeito criado é o texto que o perfil guarda (`schema.escrever_o_efeito_da_luz`): o
#: perfil anima sozinho, sem apontar para a biblioteca da interface. O valor de uma base da lista é
#: um token `base:<nome>`, que o gesto resolve em `base;cor do controle;ritmo` no ato de escolher.
GESTO_DO_EFEITO = "efeito-da-luz"
GESTO_DE_CRIAR_EFEITO = "criar-efeito"
CAMPO_DO_EFEITO = "efeito"
CAMPO_DA_DICA_DO_EFEITO = "efeito-dica"
#: O nome do controle inteiro, na dica da caixa: a janela estreita o corta com reticência.
CAMPO_DA_DICA_DA_IDENTIDADE = "identidade-dica"
SEM_EFEITO = "sem-efeito"
LUZ_FIXA = "luz-fixa"
PREFIXO_DA_BASE = "base:"
SELETOR_DOS_EFEITOS = "#seus-efeitos"
ROTULO_DA_BASE = {"respirar": "Respirar", "piscar": "Piscar",
                  "arco-iris": "Arco-íris",  # (noqa-acento) chave ASCII
                  "batimento": "Batida", "chama": "Chama", "mare": "Maré", "onda": "Onda",
                  "relampago": "Relâmpago", "reage-ao-botao": "Reage ao botão",
                  "inclinacao": "Inclinação", "dedo-no-touchpad": "Dedo no touchpad",
                  "ao-som": "Ao som"}
#: O ritmo com que cada base nasce na lista (o do desenho A): respirar 5 s, piscar 0,9 Hz, uma volta
#: do arco-íris em 12 s, batida de 1 s, a chama troca de alvo a cada ~2 s, a Maré vai e volta em
#: 8 s.
RITMO_DA_BASE = {"respirar": 2, "piscar": 3, "arco-iris": 7,  # (noqa-acento) chave ASCII
                 "batimento": 10, "chama": 5, "mare": 10, "onda": 5, "relampago": 5,
                 "reage-ao-botao": 5, "inclinacao": 5, "dedo-no-touchpad": 5, "ao-som": 5}
DICA_SEM_EFEITO = "A barra fica apagada."
DICA_LUZ_FIXA = "A cor do controle, parada."
DICA_DO_EFEITO_CRIADO = "Um efeito que você montou."
DICA_DA_BASE = {
    "respirar": "A cor sobe e desce devagar.",
    "batimento": "Duas subidas e uma pausa.",
    "chama": "O brilho oscila, sem padrão.",
    "mare": "Vai e volta para uma cor vizinha.",
    "piscar": "Lampejos da cor, de borda suave.",
    "arco-iris": "As cores giram em cada controle.",  # (noqa-acento) identificador ASCII
    "onda": "Uma onda de luz passa pela barra.",
    "relampago": "Clarões curtos, de borda suave.",
    "reage-ao-botao": "A cor do botão que você aperta.",
    "inclinacao": "A cor muda ao inclinar o controle.",
    "dedo-no-touchpad": "A cor segue o dedo no touchpad.",
    "ao-som": "A luz acompanha o som que toca.",
}
#: Os grupos da lista, na ordem do desenho: o que a pessoa vê, não o nome técnico do efeito.
GRUPOS_DA_LISTA = (
    ("Parado", (SEM_EFEITO, LUZ_FIXA)),
    ("Que respira", ("respirar", "batimento", "chama", "mare")),
    ("Que se move", ("piscar", "arco-iris", "onda", "relampago")),  # (noqa-acento) chave ASCII
    ("Que reage", ("reage-ao-botao", "inclinacao", "dedo-no-touchpad", "ao-som")),
)


def token_da_base(base: str) -> str:
    """O valor da lista para uma base: `base:respirar`."""
    return f"{PREFIXO_DA_BASE}{base}"


def base_do_token(valor: str) -> str | None:
    """A base de um valor `base:<nome>` da lista, ou `None` (não é token, ou a base é de fora)."""
    if not valor.startswith(PREFIXO_DA_BASE):
        return None
    base = valor[len(PREFIXO_DA_BASE):]
    return base if base in RITMO_DA_BASE else None


def rotulo_da_opcao(valor: str) -> str:
    """O rótulo da lista para `sem-efeito`, `luz-fixa` ou `base:<nome>`."""
    if valor == SEM_EFEITO:
        return "Sem efeito"
    if valor == LUZ_FIXA:
        return "Luz fixa"
    return ROTULO_DA_BASE[base_do_token(valor) or ""]


def dica_do_efeito(valor: str) -> str:
    """A frase de uma linha sob a lista: a da opção escolhida; um efeito criado diz o que é."""
    if valor == SEM_EFEITO:
        return DICA_SEM_EFEITO
    if valor == LUZ_FIXA or not valor:
        return DICA_LUZ_FIXA
    base = base_do_token(valor)
    return DICA_DA_BASE[base] if base else DICA_DO_EFEITO_CRIADO


def valores_da_biblioteca(biblioteca: dict[str, Any] | None = None) -> frozenset[str]:
    """Os textos de perfil dos efeitos que a pessoa criou (o que a lista põe em «Seus efeitos»)."""
    guardados = meus_efeitos("luz") if biblioteca is None else biblioteca
    return frozenset(v for v in (efeito_do_item(i) for i in guardados.values()) if v is not None)


def cor_da_base(cor: tuple[int, int, int]) -> tuple[int, int, int]:
    """A cor com que uma base da lista nasce: a do controle; a barra preta vira branca."""
    return cor if cor != (0, 0, 0) else (255, 255, 255)


def valor_da_lista_para(texto: str | None, proprios: frozenset[str] = frozenset(),
                        cor: tuple[int, int, int] | None = None) -> str:
    """O que a lista mostra para o texto que o perfil guarda.

    Um efeito que a pessoa criou aparece pelo texto dele. Um texto que não é de nenhum criado, tem o
    ritmo com que a base nasce na lista e a cor que o controle acende agora (o arco-íris não leva
    cor) é a própria base (`base:respirar`): a lista a escolheu. Qualquer outro texto fica como está
    (a lista o oferece com o nome da base, em «Seus efeitos»): a barra faz o que o texto diz, não o
    que a base diria, e a lista não mente.
    """
    from hefesto_dualsense4unix.profiles.schema import ler_o_efeito_da_luz

    if not texto:
        return LUZ_FIXA
    if texto in proprios:
        return texto
    lido = ler_o_efeito_da_luz(texto)
    if lido is None or RITMO_DA_BASE.get(lido.base) != lido.ritmo:
        return texto
    if lido.base in BASES_SEM_COR_DA_LUZ:
        return token_da_base(lido.base) if not lido.cores else texto
    if cor is not None and lido.cores == (cor_da_base(cor),):
        return token_da_base(lido.base)
    return texto


def efeito_do_item(item: Any) -> str | None:
    """O texto de perfil de um efeito da biblioteca (`{nome, base, parametros}`), ou `None`."""
    from hefesto_dualsense4unix.profiles.schema import (
        RITMO_PADRAO_DA_LUZ,
        escrever_o_efeito_da_luz,
        ler_o_efeito_da_luz,
    )

    if not isinstance(item, dict):
        return None
    par = item.get("parametros")
    par = par if isinstance(par, dict) else {}
    cores = [c.strip() for c in str(par.get("cores") or "").split(",") if c.strip()]
    try:
        ritmo = int(par.get("ritmo", RITMO_PADRAO_DA_LUZ))
    except (TypeError, ValueError):
        ritmo = RITMO_PADRAO_DA_LUZ
    texto = escrever_o_efeito_da_luz(str(item.get("base") or ""), cores, ritmo)
    return texto if ler_o_efeito_da_luz(texto) is not None else None


def opcoes_do_efeito(biblioteca: dict[str, Any] | None = None,
                     escolhido: str | None = None,
                     cor: tuple[int, int, int] | None = None) -> str:
    """As opções da lista: os grupos «Parado», «Que respira», «Que se move» e «Seus efeitos».

    `escolhido` é o efeito do perfil quando nem a lista nem a biblioteca o dizem (um perfil
    importado, ou um efeito que a pessoa apagou da biblioteca): ele entra com o nome da base, para a
    lista nunca ficar em branco nem mentir que a luz é fixa.
    """
    import html as _html

    guardados = meus_efeitos("luz") if biblioteca is None else biblioteca
    proprios: list[tuple[str, str]] = []
    for nome, item in sorted(guardados.items()):
        valor = efeito_do_item(item)
        if valor is not None:
            proprios.append((nome, valor))
    partes = []
    for rotulo_do_grupo, nomes in GRUPOS_DA_LISTA:
        itens = "".join(
            f'<option value="{v}">{_html.escape(rotulo_da_opcao(v))}</option>'
            for v in (n if n in (SEM_EFEITO, LUZ_FIXA) else token_da_base(n) for n in nomes))
        partes.append(f'<optgroup label="{rotulo_do_grupo}">{itens}</optgroup>')
    valores = frozenset(v for _, v in proprios)
    if (escolhido and escolhido not in valores
            and valor_da_lista_para(escolhido, valores, cor) == escolhido):
        from hefesto_dualsense4unix.profiles.schema import ler_o_efeito_da_luz

        lido = ler_o_efeito_da_luz(escolhido)
        if lido is not None:
            proprios.append((ROTULO_DA_BASE[lido.base], escolhido))
    if proprios:
        itens = "".join(
            f'<option value="{_html.escape(v, quote=True)}">{_html.escape(n)}</option>'
            for n, v in proprios)
        partes.append(f'<optgroup label="Seus efeitos">{itens}</optgroup>')
    return "".join(partes)


def html_dos_efeitos(biblioteca: dict[str, Any] | None = None) -> str:
    """Um chip só, «Seus efeitos: N», com os nomes na dica; sem efeito criado, nada.

    Um chip por efeito quebrava a linha da barra «Criar efeitos novos» a partir do terceiro, e a
    aba rolava a 1212 px (O-ILUMINACAO-NAO-ROLA-COM-OS-EFEITOS-CRIADOS-01, variante A). Cada
    efeito já está na lista do «Efeito» de cada controle, no grupo «Seus efeitos».
    """
    import html as _html

    guardados = meus_efeitos("luz") if biblioteca is None else biblioteca
    nomes = [nome for nome, item in sorted(guardados.items()) if efeito_do_item(item) is not None]
    if not nomes:
        return ""
    if len(nomes) == 1:
        dica = f"{nomes[0]}. Está na lista do Efeito, em Seus efeitos"
    else:
        dica = (f"{', '.join(nomes[:-1])} e {nomes[-1]}. "
                "Cada um está na lista do Efeito, em Seus efeitos")
    return (f'<span class="meu conta" tabindex="0" data-dica="{_html.escape(dica, quote=True)}">'
            f'<i style="--cor:var(--purple)"></i>Seus efeitos: {len(nomes)}</span>')


def efeito_do_controle(p: dict[str, Any] | None, uniq: str) -> str | None:
    """O efeito do controle no perfil CRU: o do override, senão o do perfil. `None` = luz fixa."""
    if not isinstance(p, dict):
        return None
    leds = p.get("leds")
    do_perfil = leds.get(CAMPO_DO_EFEITO) if isinstance(leds, dict) else None
    alvo = chave_do_override(uniq)
    meu = next((v for k, v in (p.get("controllers") or {}).items()
                if chave_do_override(str(k)) == alvo), None)
    seus = meu.get("leds") if isinstance(meu, dict) else None
    if isinstance(seus, dict) and CAMPO_DO_EFEITO in seus:
        return seus[CAMPO_DO_EFEITO] or None
    return do_perfil or None


def perfil_da_lista_de_efeito(p: dict[str, Any] | None) -> dict[str, Any] | None:
    """O perfil de onde a lista de efeitos lê: o ativo, ou, SEM perfil ativo, o do computador.

    O efeito que a pessoa escolheu sem perfil ativo vai ao ``maquina.json`` (o padrão do
    computador); ler o perfil vazio ali mostrava «Luz fixa» sobre um efeito guardado.
    """
    if p:
        return p
    try:
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            o_computador,
            perfil_que_vale,
            perfil_vazio,
        )

        vista = perfil_que_vale(perfil_vazio(), o_computador())
        return vista.model_dump(mode="json", exclude_unset=True)
    except Exception:
        return p


def escolha_da_lista(p: dict[str, Any] | None, uniq: str, brilho: float | None,
                     proprios: frozenset[str] = frozenset(),
                     cor: tuple[int, int, int] | None = None) -> str:
    """O que a lista de efeitos mostra: Sem efeito (barra apagada), o efeito, ou Luz fixa."""
    if brilho is not None and brilho <= 0.0:
        return SEM_EFEITO
    return valor_da_lista_para(
        efeito_do_controle(perfil_da_lista_de_efeito(p), uniq), proprios, cor)


@registrar("04-iluminacao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    p = perfil.ativo_que_vale(ctx.state.get("active_profile"))
    modo_da_aba = modo_da_luz_do_perfil(p)

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

    #: o nome que o usuário deu a cada controle (o `Alias`), pelo leitor único; a «Modelo» o diz
    nomes_dela = nomes_dos_donos()
    pecas = _as_pecas_da_mesa(ctx, p)
    cor_de = [peca["cor"] for peca in pecas]
    casas = as_casas_da_mesa(pecas)

    colunas: dict[str, dict[str, Any]] = {}
    #: A LUZ DO DESENHO GRANDE, por LUGAR — ver `folha_da_luz`. Ela nasce vazia
    #: e só recebe quem tem controle: `folha_da_luz` APAGA todo lugar que não
    luz_do_desenho: dict[str, tuple[str, int | None]] = {}
    biblioteca = meus_efeitos("luz")
    criados = valores_da_biblioteca(biblioteca)
    do_efeito = perfil_da_lista_de_efeito(p)
    listas_de_efeito: dict[str, str] = {}
    for c, cor_dele in zip(ctx.conectados, cor_de, strict=True):
        uniq = str(c.get("uniq") or "")
        crua = cor_do_swatch(c)
        b = brilho_aceso(c, p, uniq)
        pct = None if b is None else round(float(b) * 100)
        casa = _da_mesa(ctx, uniq)
        n = _numero(ctx, c)
        nome = str(casa.get("nome") or "—")
        via = str(casa.get("via") or (c.get("transport") or "").upper() or "—")
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
            listas_de_efeito[f'[data-controle="{casa["pref"]}"] select.g4-efeito'] = (
                opcoes_do_efeito(biblioteca, efeito_do_controle(do_efeito, uniq), cor_dele))
        na_lista = escolha_da_lista(
            do_efeito, uniq, None if b is None else float(b), criados, cor_dele)
        identidade = " • ".join(partes_do_modelo(
            {"jogador": n, "dono": o_nome_de(nomes_dela, uniq), "nome": nome, "via": via}))
        colunas[uniq] = {
            "brilho": "—" if pct is None else f"{pct}%",
            CAMPO_DO_EFEITO: na_lista,
            CAMPO_DA_DICA_DO_EFEITO: dica_do_efeito(na_lista),
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
            "identidade": identidade,
            CAMPO_DA_DICA_DA_IDENTIDADE: identidade,
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
        #: O MODO DA ABA: o quadro leva o modo no `data-modo-da-aba` (a folha deixa as colunas
        #: paradas no Automático), e cada botão do par acende pelo modo do perfil.
        GESTO_DO_MODO: modo_da_aba,
        f"{GESTO_DO_MODO}-{MODO_AUTOMATICO}": "sim" if modo_da_aba == MODO_AUTOMATICO else "",
        f"{GESTO_DO_MODO}-{MODO_PERSONALIZADO}":
            "sim" if modo_da_aba == MODO_PERSONALIZADO else "",
        #: `perfil` saiu em 13/09/2026: o chip é das dez, dono `pacotes.topo()`.
        "sem_dono": {},
        "blocos": {SECAO_DA_TROCA: secao_da_troca(ctx.mesa),
                   SELETOR_DOS_EFEITOS: html_dos_efeitos(biblioteca),
                   **listas_de_efeito,
                   "#plastico-vivo": (_folha_do_plastico(ctx.mesa, CAIXA_DA_COLUNA)
                                      + folha_da_luz(luz_do_desenho))},
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }


from . import gesto  # noqa: E402


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde o usuário clicou. Vazio = clique solto, e recusa."""
    return str(o.get("uniq") or "")


def sem_resposta_do_daemon() -> str:
    """A frase de "o Hefesto não respondeu" — e ela é do MOTOR, não daqui.

    Até 02/09/2026 os botões `cor`, `apagar` e `auto` jogavam fora o booleano de
    `p.led_set(...)`/`p.chamar(...)`. `ipc_bridge._safe_call` devolve `(False, None)` para daemon
    offline, socket ausente, timeout e erro JSON-RPC, e o clique sumia sem uma palavra (o quarto
    gesto, `player`, já lia `(ok, motivo)`).

    A frase é `lightbar_actions._AVISO_HEFESTO_DESLIGADO`, a da janela GTK no mesmo evento (duas
    telas dizendo coisas diferentes do mesmo daemon desligado seria a segunda verdade). É privada
    por convenção de nome, como o `lightbar_actions` lê `footer_actions._lista_de_secoes`; RELATADO:
    merece nome público, em `app/actions/lightbar_actions.py`, fora deste arquivo. Já vem hedged
    (*"o Hefesto **pode** estar desligado"*): o `bool` do bridge colapsa quatro causas, e afirmar
    uma seria inventar diagnóstico.
    """
    from hefesto_dualsense4unix.app.actions import lightbar_actions

    return str(lightbar_actions._AVISO_HEFESTO_DESLIGADO)


def _so_abriu_o_seletor(o: dict[str, Any]) -> bool:
    """O clique é a ABERTURA de um `<input>`, e não uma escolha do usuário.

    `tipo` (o `tagName`) e `evento` (o `ev.type`) vêm do BOOTSTRAP em todo clique. Um `<input
    type="color">` dispara `click` ao abrir, com o valor VELHO, e `change` ao confirmar; só o
    segundo é pedido. Sem `evento` no clique nada muda (as provas do contrato chamam o gesto com a
    carga mínima): só fecha quando os DOIS campos dizem abertura.

    Vale para o trilho (03/09/2026) com o tempo invertido: um `<input type="range">` clicado na
    pista dispara `input`, `change` e depois `click`; o BOOTSTRAP escuta `change` e `click`, e sem o
    guarda cada clique viraria DUAS gravações no perfil e DUAS escritas no rádio. Nos dois casos o
    pedido é o `change` e a resposta certa é sair calado (recusar dizendo poria erro na tela por um
    gesto feito uma vez). O seletor de cor saiu da guia (:data:`FORA_DA_GUIA`, 11/09/2026) e o
    guarda FICA, chamado hoje pelo `brilho`; a medição do caso de cor explica por que ele existe
    (não é só para `range`).
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

    Não é uma janela e não precisa ser. As leituras que decidem a frase de um desfecho
    (`alvo_fora_da_mesa`, `modo_nativo_manda_no_output`, `mesa_vazia`) perguntam por `getattr` a um
    objeto qualquer; a GUI estável passa a si mesma e a aba Status as publica a cada tique do
    `state_full` (`status_actions.py`: `_target_uniq_by_index` em `_update_target_maps`,
    `_modo_nativo_ligado` em `_sync_modo_nativo_manda_no_output`, `_coop_ligado` em
    `_sync_coop_governa_luzes`). Esta interface tem os MESMOS dados (`ctx.state` é o `state_full`);
    falta o objeto com os nomes que o dono da frase conhece. Nenhuma regra de texto se reescreve
    deste lado.
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

    É o `_aplicar_cor_no_controle` da GTK (`app/actions/lightbar_actions.py`) no que esta tela pode
    ter.

    **Guarda de cor única** (desde 08/09/2026). `escolha=True` a liga no gesto que ESCOLHE um tom
    (`cor`). `apagar` passa por fora (manda preto, ausência
    de cor); `brilho` reenvia a cor que o controle JÁ TEM com outro fator, e deslocá-la trocaria a
    cor dela num arraste.

    :return: o RECADO quando a cor pedida foi deslocada, senão `None`.

    **`brilho` chega pronto ou se pergunta ao perfil** (03/09/2026, o trilho que grava). Os gestos
    de COR pintam com o guardado: o default `_DO_PERFIL` lê `brilho_aceso`, o MESMO número que a
    coluna imprime. O `brilho` passa o valor porque precisa aplicar o que ela ACABOU de escolher,
    sem depender de a gravação em disco ter acontecido (um disco que recusasse a escrita levaria
    junto a aplicação).

    **1. O brilho viaja junto.** `p.led_set(rgb, uniq=uniq)` sem o argumento fazia o `led.set` cair
    no default *"Ausente ou inválido -> assume 1.0"* (`ipc_handlers._handle_led_set`; o
    `_payload_led_set` só põe o campo se passado): a coluna com `50%` no trilho mandava a cor a
    100%, desfazendo o brilho calada. A GTK manda `brightness=self._current_brightness` em toda
    escrita; aqui sai de `brilho_aceso`.

    **2. O desfecho se lê do corpo do daemon.** `led_set` (`bool`) `True` só diz *"o daemon
    respondeu"*. O corpo do `led.set` publica `aplicado_em`/`guardado_em` (APLICAR-VERDADE-01;
    `led_set_detalhado` os entrega). Sem eles, com o modo nativo ligado (o backend muta toda escrita
    de output) ou com o controle recém-saído da mesa, o clique saía **calado**: o piloto anotava
    "aplicou" e a barra não mudava.

    A frase é só de `textos_de_aplicacao.frase_do_desfecho`: `frase_do_envio` a chama e troca
    *"aplicado"* por *"enviada"* no ramo feliz, porque por Bluetooth o firmware ACEITA E IGNORA
    escritas de cor (medição em `_TOAST_COR_ENVIADA`, 330 mil escritas ignoradas com a barra
    apagada). O `RuntimeError` no ramo do guardado não é "recusa": entre a frase no cartão e o
    silêncio, o silêncio é a mentira; a GTK diz a mesma frase num toast neutro.

    Por que o desfecho não escolhe o tom (fato substituído em 04/09/2026: o canal de aviso existe,
    `{"recado": …}` pousa no cartão com tom de sucesso e vida de 6 s, o `brilho` o usa; desde
    13/09/2026 a frase vai ao diário da janela, TELA-CALADA-01 e FRASES-E-DICAS-01): este caminho
    não sabe QUAL dos desfechos aconteceu, `frase_do_desfecho` devolve UMA frase com as quatro
    razões (recusa explicada, aplicado, guardado, nada aconteceu) já colapsadas, e reler
    `destinos_da_aplicacao` aqui seria a segunda verdade sobre o payload (a ELO-MUDO-01 a inverteu:
    *"antes a janela deduzia e o daemon era ignorado"*). O laranja é o erro mais barato. RELATO: um
    segundo retorno de `frase_do_desfecho` dizendo qual destino venceu fecharia isto para as dez
    abas (`app/textos_de_aplicacao.py`, fora deste arquivo). Por isso a comparação é com a frase
    FELIZ, não com `aplicado_em`, e cala quando é a do caminho feliz.
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

    A-04-PERGUNTA-AO-DAEMON-VIVO-01. É o que o perfil ATIVO dá ao controle (`brilho_do_controle`: o
    próprio ou o do perfil) e o que o disco guarda depois do gesto (`_com_a_cor_gravada`). Quem
    apagou pelo «Desligar» tem 0% gravado, e vale o do perfil, que ele herda quando o 0% sai.
    Conferência de 25/09/2026: o «Desligar» atravessa a troca automática pela camada viva e o perfil
    do jogo pode ter brilho próprio para o controle; ler só o do perfil acendia no brilho errado e
    APAGAVA do disco o brilho gravado ali. Perfil a 0% (mesa inteira apagada) ou sem o campo legível
    acende cheio: a cor escolhida tem de aparecer.
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

    A-04-PERGUNTA-AO-DAEMON-VIVO-01 (25/09/2026). Gravar o preto como a COR do controle falhava
    desde 22/09, quando o preto deixou de ser cor (`led_control.cor_escolhida`, ordem de produto:
    *"vamos banir esse preto de aparecer"*): o perfil reaplicado lia «não opinou» e acendia a barra
    (medido na mesa de quatro: o P2 apagado voltava vermelho na troca manual, no boot e no «Salvar
    perfil», e o preto apagava do disco o laranja dela). O caminho de apagar que aquela decisão
    deixou é o brilho, *"um campo que só a mão do usuário move"*. Os mesmos dois estados sem onde
    gravar de `_guardar_a_cor_no_perfil`, e a mesma razão para sair calado: a barra já apagou.
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
    """A cor que o usuário ESCOLHEU vai ao disco, no override daquele controle.

    Medido na bancada em 09/09/2026, duas caras que o usuário viu como uma: *"o controle branco fica
    oscilando entre a cor que eu seleciono e
    a cor azul. fora que o slicer tá estranho ainda"* # noqa-acento: citação literal

        no disco, o override do branco  {"leds": {"lightbar_brightness": 0.49}}
        a cor que o usuário escolheu           em lugar NENHUM

    `_escrever_a_cor` mandava a cor só ao daemon (`led_set_detalhado`), na camada VIVA por-uniq:
    acende e some no primeiro evento que faça o resolvedor reler o perfil (replug, `profile.switch`,
    reaplicação). Embaixo fica a camada automática, `player_slot_color(1)` = `#0000FF`, ou o global
    dela, `#2850B4`: os dois são azuis, e é o azul que ela via voltar. Mesma raiz do trilho: sem cor
    no disco o gesto `brilho` só adivinhava a cor pela luz ACESA, já escalada (D8), e reescalava:
    `#2850B4` a 80% -> 60% -> 70% -> 80% desceu para `(19,38,86)`, `(13,26,60)`, `(10,20,48)`;
    **subindo o brilho, a cor escurecia** até o preto (ver a escada em `brilho`).

    `_com_a_cor_gravada` já carimba a PROCEDÊNCIA (`lightbar_para_o_numero`) que `cores_sem_colisao`
    lê para não fossilizar a escolha, e só tinha UM chamador (desligar o automático); a escolha de
    um tom nunca passou por ele (fechado em 08/09/2026).

    Quem grava a cor é quem a escolhe: um tom (`cor`, `escolha=True`). O «Desligar»
    grava o brilho em 0% em `_guardar_o_apagado_no_perfil` (o preto não é cor desde 22/09) e o
    `brilho` passa por fora: gravar ali congelaria no perfil uma cor que ela não pediu. `religar` é
    a cor escolhida numa barra em 0%: o 0% do controle sai do override e ele volta ao brilho do
    perfil, o mesmo em que o `_escrever_a_cor` a acendeu.

    Sem perfil no disco não há onde guardar e o gesto sai calado: a cor JÁ está no aparelho e um
    cartão de recusa depois do ato diria que o produto não fez o que fez (o gesto `brilho` recusa na
    ENTRADA, onde ainda dá). São dois estados: `active_profile` vazio, e o que nomeia um perfil que
    o disco não tem (`FileNotFoundError: perfil não encontrado`; sete réguas caíram nele ao montar
    contexto com perfil ativo sem semear arquivo). **A gravação é a SEGUNDA metade do gesto e não
    pode derrubar a primeira**, já no plástico dela.

    O `except` é estreito de propósito, só `OSError`: um `except Exception` engoliria o
    `ValidationError` de um perfil malformado e a cor sumiria do arquivo em silêncio, o defeito que
    a função existe para matar.
    """
    nome = perfil.nome_do_ativo(ctx.state).strip()
    dele = next((c for c in ctx.conectados
                 if str(c.get("uniq") or "") == uniq), None)
    numero = _numero(ctx, dele) if dele is not None else None
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    efeito = _a_base_na_cor_nova(ctx, nome, dele, rgb) if dele is not None else None
    with contextlib.suppress(OSError):
        gravar_pelo_gesto(
            "luz", nome,
            lambda prof: _com_a_cor_gravada(prof, uniq, rgb, numero, religar=religar,
                                            efeito=efeito),
            uniq=uniq, origem="interface-nova")


def _a_base_na_cor_nova(ctx: Contexto, nome: str, c: dict[str, Any],
                        rgb: tuple[int, int, int]) -> str | None:
    """O texto da base da lista que este controle anima, reescrito na cor nova; `None` se não há.

    A base nasce com a cor do controle daquele instante (`efeito_da_luz`). Trocar a cor depois sem
    reescrever o efeito deixava a barra animando a cor velha, com a linha Cor dizendo a nova e a
    lista mudando para «Seus efeitos». O arco-íris não leva cor, e um efeito que a pessoa criou
    é do usuário: nenhum dos dois muda.
    """
    from hefesto_dualsense4unix.profiles.schema import escrever_o_efeito_da_luz

    cru = perfil.ativo_que_vale(nome)
    uniq = str(c.get("uniq") or "")
    hoje = valor_da_lista_para(efeito_do_controle(perfil_da_lista_de_efeito(cru), uniq),
                               valores_da_biblioteca(), _a_cor_de_agora(ctx, cru, c))
    base = base_do_token(hoje)
    if base is None or base in BASES_SEM_COR_DA_LUZ:
        return None
    r, g, b = cor_da_base(rgb)
    return escrever_o_efeito_da_luz(base, [f"{r:02X}{g:02X}{b:02X}"], RITMO_DA_BASE[base])


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

    O `state_full` publica o `modelo` (nome de fábrica respondido pelo aparelho) e a mesa da tela
    carrega a `cor` (o `id` da linha do mapa); qualquer um vai a `cor_do_plastico.tom_da_luz`, a
    regra do provider do daemon. `None` quando o plástico não foi lido ou não tem tom, e a cor
    automática é a do número.
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


@gesto("04-iluminacao.html", "cor", grava="gravar_pelo_gesto")
def cor(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O usuário clicou num tom. A cor vai AO CONTROLE NA HORA.

    Decisão de 01/09/2026 (*"clicar na cor já deveria aplicar a cor no controle."*), que vale para a
    interface inteira: **o gesto age na hora**, sem rascunho à espera de "Aplicar". A cor chega pelo
    `led.set` direto; o "Salvar perfil" continua sendo o que grava.

    A conversão não mora aqui (até 02/09/2026 era `tuple(int(hexa[i:i + 2], 16) …)`): é
    `core/led_control.hex_to_rgb`, que RECUSA DIZENDO (`ValueError`: *"hex_to_rgb espera formato
    RRGGBB"*, *"componente não numérico"*).

    Uma porta só, desde 11/09/2026: a segunda era o seletor de cores do sistema (casa hachurada no
    fim da fileira, sem `data-hex`, com a cor no `valor`), que saiu por ordem de produto
    (:data:`FORA_DA_GUIA`) com a queda pelo `valor`: peça sem chamador o portão `casa-sabe` acusa, e
    **peça com chamador e sem tela é pior**, aceita calada carga que ninguém desenhou. Sem `hex`,
    RECUSA DIZENDO: todo botão da fileira nasce com `data-hex`, o pedido sem ele é carga inventada
    ou endereço envelhecido; sair calado esconderia o defeito e adivinhar pelo `valor` ressuscitaria
    a porta fechada.

    A guarda `_so_abriu_o_seletor` era chamada aqui porque o campo de cor dispara `click` ao ABRIR
    (valor velho) e `change` ao confirmar (medido com o BOOTSTRAP real num Chrome, 02/09/2026:
    `{gesto:'cor', hex:'', valor:'#0000ff', tipo:'input', evento:'click'}` ao abrir,
    `valor:'#12ab34', evento:'change'` ao escolher); sem ela abrir e CANCELAR deixava a barra numa
    cor nunca pedida. Continua viva (o `brilho` a chama, com o tempo invertido), mas um botão da
    guia não abre nada.

    O desfecho se lê (02/09/2026, ver `sem_resposta_do_daemon`) e o brilho viaja junto (03/09/2026,
    ver `_escrever_a_cor`: este gesto DESFAZIA o brilho a cada clique). Duas peças nunca ficam da
    mesma cor (08/09/2026): o alvo é UM controle, então o tom do vizinho é uma escolha e não um
    broadcast, e `_escrever_a_cor(..., escolha=True)` devolve a frase que diz DE QUEM é a cor.
    Clicar na amostra já acesa reenvia a mesma cor: desde 16/10/2026 é este o reenvio (a caixa do
    hexadecimal, que era o botão dele, saiu da tela).
    """
    _nao_no_automatico(ctx)
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

    Não é `lightbar.reset` (esse devolve a cor AUTOMÁTICA, o outro botão). O desfecho se lê como no
    `cor` (`sem_resposta_do_daemon`): sem resposta, "Desligar" deixa a barra ACESA, a cara de "não
    cliquei direito".

    O apagado é o brilho, não a cor (D-2509-O-DESLIGAR-E-O-BRILHO-EM-ZERO,
    A-04-PERGUNTA-AO-DAEMON-VIVO-01, 25/09/2026): o preto ia ao disco como a cor e desde 22/09 o
    preto é «não opinou», então a troca manual, o boot e o «Salvar perfil» acendiam a barra de novo
    e o laranja escolhido se perdia. O brilho em 0% sobrevive a reaplicar o perfil
    (`_guardar_o_apagado_no_perfil`); para acender, o trilho ou um tom da guia (`_escrever_a_cor`,
    `religar`). Pelo mesmo caminho de escrita, com brilho 0: o preto que sai é `int(c * 0)` e o
    daemon guarda o 0%.
    """
    _nao_no_automatico(ctx)
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("apagar: o clique não disse em qual controle")
    _escrever_a_cor(ctx, p, uniq, (0, 0, 0), apagando=True, brilho=0.0)


def _pct_pedido(o: dict[str, Any]) -> int:
    """Os 0-100 que o trilho mandou, validados PELO ESQUEMA e não por uma conta local.

    A faixa é de `app/draft_config.LedsDraft.lightbar_brightness` (`int, ge=0, le=100`, o campo que
    o `GtkScale` da janela estável alimenta); digitar `0 <= n <= 100` aqui seria a segunda
    declaração. Aqui só se traduz a recusa do pydantic para frase de tela. `valor` é a porta: o
    BOOTSTRAP o manda de todo elemento com `value` (num `<input type="range">`, a posição do
    polegar, como string).
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

    A conta é de `app/draft_config._leds_draft_to_config` (o `/100.0` do "Salvar perfil" da janela
    estável). As escalas convivem de propósito: `LedsDraft` `int 0-100` (a tela) e `LedsConfig`
    `float 0.0-1.0` (o disco). Privado por convenção de nome, como
    `lightbar_actions._AVISO_HEFESTO_DESLIGADO`; RELATADO: merece nome público em
    `app/draft_config.py`, fora deste arquivo.
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

    `None` evita o barulho (regra do `_com_os_gatilhos` da aba Gatilhos): regravar um perfil
    idêntico troca a data do arquivo e cria um backup em `.historico/` por um arraste que voltou ao
    mesmo lugar.

    O alvo é o override do controle, não a seção global (`ControllerOverrides.leds` desde a
    PERFIL-02; `manager._controllers_to_led_scales` distribui o brilho por MAC). Esta aba não tem
    outro alvo: a fita do topo é INERTE aqui desde 28/08 (os quatro controles lado a lado, *"não há
    escolhido"*), cada trilho pertence a UMA coluna; no global o trilho do P2 mudaria o brilho do P1
    (a contradição que o `_janela_do_desfecho` anota sobre o ramo "Todos").

    A fusão é por campo (PERFIL-01: override PARCIAL nunca apaga o global no replug), por isso o
    ramo do `model_copy`: os overrides do disco são `{"lightbar": [255, 0, 0]}` e nada mais, e
    trocar a seção inteira apagaria a cor escolhida. `save_profile` serializa com `exclude_unset`, o
    não tocado segue ausente do arquivo.
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

    Decisão de 03/09/2026 ("Grava na hora"). O trilho já era desenhado como slider (`.cheio::after`
    põe um knob de 12px) e não fazia nada (*"a maior falta desta aba"* em
    `docs/data/paridade-gtk-html.csv`). Gravar é a única saída coerente: a interface não tem
    rascunho (decisão de 01/09) e o disco é o que a troca de perfil reaplica; sem gravar o valor
    voltaria ao velho no primeiro perfil reaplicado. O número que a coluna imprime é o que o daemon
    acende (`brilho_aceso`, desde 25/09/2026); o do disco é a queda.

    Os três tempos, nesta ordem:

        1. a COR PEDIDA sai da tela com o brilho VELHO: `_a_cor_de_agora` inverte a escala do daemon
        (D8, `lightbar_rgb` PÓS-escala), e invertê-la com o NOVO devolveria uma cor nunca pedida; 2.
        o DISCO recebe o número novo (a promessa do gesto, o que sobrevive a um `profile.switch`);
        3. o APARELHO recebe a mesma cor com o brilho NOVO, pelo parâmetro e não relido do disco: um
        disco cheio não apaga a barra.

    Escreve no disco do usuário e por isso entra em `hefesto_vivo.PERIGOSOS` (a prova botão a botão
    arrastaria o trilho e gravaria no perfil ATIVO; molde do `("*", "salvar")` e do `guardar` da aba
    Gatilhos). Não é `perfil.gravar_e_reaplicar`: termina em `profile_switch`, que reaplica o perfil
    INTEIRO e reacende a barra que ela DESLIGOU (medido em 03/09 em
    `a03_gatilhos._gravar_so_o_gatilho`).

    O `click` que vem depois do `change` não é um segundo pedido: `<input type="range">` clicado na
    pista dispara `input`, `change` e `click` e o BOOTSTRAP escuta os dois últimos; sem
    `_so_abriu_o_seletor` gravaria DUAS vezes e mandaria DUAS escritas ao rádio.

    Sem cor conhecida (a Steam com o `fd`, cor desconhecida) não há cor a reescalar e mandar preto
    APAGARIA a barra por um arraste: o número vai ao disco e o cartão diz que a barra não mudou
    agora (entre a frase e o silêncio, o silêncio é a mentira). A frase é curta, decisão [04] de
    04/09/2026 entre a inteira, a curta e o silêncio: a longa gastava três linhas *"repetindo com
    palavras o que a tira tracejada já mostra sem palavra nenhuma"*; fica quanto foi guardado e a
    causa, que vem do MOTOR, palavra por palavra. Sai como `{"recado": …}` (canal de aviso da
    ONDA0-P/D-01, tom de sucesso, 6 s), não `RuntimeError`, que no piloto é a RECUSA (laranja, 30 s)
    e mentiria: o brilho ESTÁ no disco. Desde 13/09/2026 a frase vai ao diário da janela
    (TELA-CALADA-01 e FRASES-E-DICAS-01).

    :return: `{"recado": …}` quando o número foi guardado e a barra não pôde mudar; `None` no
    caminho feliz (cartão com a frase padrão).
    """
    _nao_no_automatico(ctx)
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
    # Duas funções do mesmo arquivo, o mesmo
    # grava a escolha do usuário; ver `_guardar_a_cor_no_perfil`.
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
    """O usuário clicou numa pílula da linha LEDs: Fraco, Médio ou Forte."""
    _nao_no_automatico(ctx)
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

    É a PEDIDA, não a publicada: `lightbar_rgb` vem PÓS-escala (D8), e gravá-lo escureceria a cor do
    perfil a cada volta (a 50%, `#0000FF` viraria `#00007F` no disco e seria escalado de novo).
    `cor_escolhida` inverte a escala, o caminho da caixa `#RRGGBB`.

    É o dono da marca da fileira (A-MARCA-DA-COR-NAO-SOME-01, 24/09/2026), queixa: *"quando eu
    abaixo o volume do lightbar,. o X não permanece no seletor dos demais controles"*
    <!-- noqa-acento: citação literal -->
    A borda do controle, o X dos outros, a recusa do tom tomado e a cor que o trilho reenvia saem
    daqui, pela escada:

        1. a luz acesa, quando ela diz o tom (`_o_tom_que_acende`);
        2. a cor que o usuário escolheu para ESTE controle, no perfil, menos a FÓSSIL que o daemon
        trocou pela do número (`_a_cor_guardada_que_vale`); 3. com a paleta automática desligada, a
        cor GLOBAL do perfil, antes do brilho (`_a_cor_do_global`); sem global, a luz como está; 4.
        a cor automática (`led_control.cor_automatica`): a do plástico, e a do número sem ela
        (D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO).

    O degrau 1 sozinho não segurava a marca (o piloto mediu os três buracos com o clique): meio
    segundo depois de SOLTAR o trilho o disco tem o brilho novo e o daemon ainda publica a luz
    velha; a 0% todo tom acende preto; subindo de 0% a luz velha ainda é o preto. A cor do controle
    não mudou (brilho não é cor): quem sabe é o disco ou a paleta. A luz vem PRIMEIRO porque é o que
    o plástico mostra, inclusive quando a gravada é fóssil.

    O degrau 3 lê o GLOBAL e não a luz (conferência de 24/09/2026): devolver a luz acesa fazia, com
    as «Cores automáticas por controle» desligadas, os buracos voltarem (medido na mesa de quatro: o
    controle sem cor gravada perdia borda e X ao soltar, a 0% a marca pulava para a cor do NÚMERO, e
    subir de 0% acendia nessa cor; com global fora da guia, `#2850B4`, o trilho reenviava a luz já
    escalada e a barra escurecia a cada arraste). Regra de produto: *"nunca é pensada só em um
    modo"*.

    :param cru: o perfil como DICIONÁRIO (`perfil.ativo`), não o `Profile` do pydantic:
    `brilho_do_controle` lê o JSON cru e um modelo devolveria `None` em silêncio, sumindo da
    inversão de escala e escurecendo a cor gravada.
    """
    from hefesto_dualsense4unix.core.led_control import cor_automatica
    from hefesto_dualsense4unix.interface.cartao_do_controle import cor_do_swatch

    uniq = str(c.get("uniq") or "")
    efetiva = cor_do_swatch(c)
    tom = _o_tom_que_acende(efetiva, brilho_aceso(c, cru, uniq))
    if tom is not None:
        return tom
    if modo_da_luz_do_perfil(cru) == MODO_AUTOMATICO:
        #: No modo automático a cor guardada fica no disco e NÃO vale: o hex e o X dizem a
        #: cor do plástico, que é a que o controle acende.
        return cor_automatica(_numero(ctx, c), _tom_do_plastico(c))
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
                       numero: int | None = None, *, religar: bool = False,
                       efeito: str | None = None) -> Any:
    """O perfil com a cor DESTE controle escrita no override dele.

    **A cor vai com procedência** (decisão de 08/09/2026): `LedsConfig.lightbar_para_o_numero` =
    *para qual número esta cor foi escolhida*. Aqui o produto CONGELA no arquivo a cor que cada
    controle acende, e ela é a do NÚMERO dele agora; sem o carimbo o arquivo guarda "azul" e perde
    "azul porque ele era o 1", a diferença entre escolha e fóssil (o número é de SESSÃO e gira com a
    ordem de conexão; assim os ranks 2 e 4 ficaram com as cores dos slots 1 e 2 e dois DualSense
    acenderam o mesmo `#0000FF`).

    Irmão de `_com_o_brilho_gravado`, campo por campo (a fusão é POR CAMPO: trocar a seção inteira
    por uma que só fale de cor apagaria o brilho próprio; `save_profile` usa `exclude_unset`). Ao
    contrário do irmão NÃO devolve `None` quando nada muda: aqui a escrita é a **consequência** do
    pedido e tem de acontecer nas duas hipóteses; uma cor que já é a do override precisa continuar
    lá depois de o automático sair.

    `religar=True` é a cor escolhida numa barra em 0% (A-04-PERGUNTA-AO-DAEMON-VIVO-01): o brilho
    próprio de 0% SAI do override e o controle volta ao do perfil (mesma conta de
    `_o_brilho_de_religar`). Brilho próprio ACIMA de 0 fica (é escolha do usuário, de outro perfil
    que a camada viva atravessou apagada). Com o perfil em 0% e sem brilho próprio, fica cheio,
    explícito.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, LedsConfig

    chave = chave_do_override(uniq)
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.leds
    campos: dict[str, Any] = {"lightbar": rgb}
    if efeito is not None:  # a base da lista na cor nova (`_a_base_na_cor_nova`)
        campos[CAMPO_DO_EFEITO] = efeito
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


_RECADO_DO_AUTOMATICO = (
    "Modo automático: cada controle acende a cor do plástico dele, ou a do número, e duas "
    "nunca ficam iguais. A cor que você escolheu para cada um fica guardada e volta no "
    "modo personalizado.")

_RECADO_DO_PERSONALIZADO = (
    "Modo personalizado: valem a cor, o brilho e as luzes que você escolher. Guardei a "
    "cor de cada controle que ainda não tinha uma, para nenhuma se perder e nenhuma "
    "se repetir.")


@gesto("04-iluminacao.html", GESTO_DO_MODO, grava="gravar_pelo_gesto")
def modo_da_luz(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O par «Modo automático | Modo personalizado» — e ele MUDA o perfil.

    Tomou o lugar do interruptor `auto-cores` (D-13, 04/09/2026) e levou o contrato: o Automático é
    o interruptor ligado (`leds.auto_player_colors`); o Personalizado é ele desligado, com a cor de
    cada controle gravada no ato. Pedido de 06/10/2026: par de botões no alto da aba; o Automático
    deixa PARADO o que a coluna escolhe (cor, brilho, número e luzes).

    Nada se apaga ao ir para o Automático: `leds.modo` escrito como Automático é o que o
    `ProfileManager` lê para mandar ao aparelho a cor do plástico, e a cor de cada controle fica no
    disco para o Personalizado devolver. A paleta ligada sozinha não bastava: a cor própria de um
    controle VENCE a automática na aplicação, e a tela diria Automático sobre um controle aceso na
    cor escolhida. Ao ir para o Personalizado, o controle com cor guardada (e não fóssil) a mantém;
    o sem cor recebe a que acende agora (D-13).

    A leitura de volta é do DISCO: o `data-modo` do botão diz o que o usuário PEDIU, e pedir o modo
    em que o perfil já está não grava nada. Reaplicar é metade do gesto: o modo só entra em vigor na
    ativação do perfil (`perfil.reaplicar`, como o `auto-cores` que a precedeu).
    """
    pedido = str(o.get("modo") or "")
    if pedido not in (MODO_AUTOMATICO, MODO_PERSONALIZADO):
        raise ValueError(
            f"{GESTO_DO_MODO}: o clique não disse qual modo. Cada botão do par manda o "
            f"`data-modo`; um pedido sem ele não vem da tela")

    nome = perfil.nome_do_ativo(ctx.state).strip()
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    cru = perfil.ativo_que_vale(nome)
    if modo_da_luz_do_perfil(cru) == pedido:
        return None

    def _virar(prof: Any) -> Any:
        if pedido == MODO_PERSONALIZADO:
            for c in ctx.conectados:
                uniq = str(c.get("uniq") or "")
                if not uniq or _a_cor_guardada_que_vale(ctx, cru, c) is not None:
                    continue
                prof = _com_a_cor_gravada(
                    prof, uniq, _a_cor_de_agora(ctx, cru, c), _numero(ctx, c))
        leds = prof.leds.model_copy(update={
            "modo": pedido, "auto_player_colors": pedido == MODO_AUTOMATICO})
        return prof.model_copy(update={"leds": leds})

    gravar_pelo_gesto("luz", nome, _virar, origem="interface-nova")
    perfil.reaplicar(nome, ctx, p)
    return {"recado": (_RECADO_DO_AUTOMATICO if pedido == MODO_AUTOMATICO
                       else _RECADO_DO_PERSONALIZADO)}


def _com_o_efeito_gravado(prof: Any, uniq: str, efeito: str | None, *,
                          religar: bool = False) -> Any:
    """O perfil com o efeito DESTE controle escrito no override dele (`None` = luz fixa).

    O `None` é escrito, e não tirado: o controle diz «luz fixa» mesmo quando o perfil todo tem um
    efeito. `religar` tira o 0% do controle (e põe 100% se o perfil todo está em 0%), porque um
    efeito escolhido numa barra apagada tem de aparecer; é a mesma conta da cor escolhida em
    `_com_a_cor_gravada`.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, LedsConfig

    chave = chave_do_override(uniq)
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.leds
    campos: dict[str, Any] = {CAMPO_DO_EFEITO: efeito}
    if religar:
        proprio = antes is not None and "lightbar_brightness" in antes.model_fields_set
        if antes is not None and proprio and float(antes.lightbar_brightness) <= 0.0:
            antes = LedsConfig.model_validate({
                k: getattr(antes, k) for k in antes.model_fields_set
                if k != "lightbar_brightness"})
            proprio = False
        if not proprio and float(getattr(prof.leds, "lightbar_brightness", 1.0)) <= 0.0:
            campos["lightbar_brightness"] = 1.0
    novos = LedsConfig(**campos) if antes is None else antes.model_copy(update=campos)
    atuais[chave] = dele.model_copy(update={"leds": novos})
    return prof.model_copy(update={"controllers": atuais})


@gesto("04-iluminacao.html", GESTO_DO_EFEITO, grava="gravar_pelo_gesto")
def efeito_da_luz(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A lista «Efeito» da coluna: Sem efeito, Luz fixa, uma base da lista ou um efeito criado.

    O efeito é do controle da coluna e vai ao perfil (`leds.efeito` no override dele); quem anima é
    o `luz_animada` do daemon, que cala quando o jogo pinta a barra. «Sem efeito» apaga a barra
    (o 0% do «Desligar» que saiu do topo da coluna) e «Luz fixa» devolve a cor de sempre, acendendo
    a barra se ela estava apagada. Uma base da lista (`base:respirar`) vira o texto
    `base;cor do controle;ritmo` neste ato, com a cor que a barra acende agora e o ritmo com que a
    base nasce (`RITMO_DA_BASE`); o arco-íris não leva cor. Um valor que não é nenhum dos quatro é
    recusado.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        escrever_o_efeito_da_luz,
        ler_o_efeito_da_luz,
    )

    _nao_no_automatico(ctx)
    uniq = _uniq(o)
    if not uniq:
        raise ValueError(f"{GESTO_DO_EFEITO}: o clique não disse em qual controle")
    pedido = str(o.get("valor") or "").strip()
    base = base_do_token(pedido)
    if pedido.startswith(PREFIXO_DA_BASE) and base is None:
        raise ValueError(f"{GESTO_DO_EFEITO}: a lista não tem a base {pedido!r}")
    efeito = None if pedido in (SEM_EFEITO, LUZ_FIXA) else pedido
    if base is None and efeito is not None and ler_o_efeito_da_luz(efeito) is None:
        raise ValueError(
            f"{GESTO_DO_EFEITO}: o valor {pedido!r} não é um efeito. A lista oferece "
            f"{SEM_EFEITO!r}, {LUZ_FIXA!r}, uma base ou um efeito que você criou")

    nome = perfil.nome_do_ativo(ctx.state).strip()
    perfil._com_o_src()
    cru = perfil.ativo_que_vale(nome)
    dele = next((c for c in ctx.conectados if str(c.get("uniq") or "") == uniq), None)
    if base is not None:
        if dele is None:
            raise ValueError(f"{GESTO_DO_EFEITO}: o controle da coluna não está ligado")
        cor = _a_cor_de_agora(ctx, cru, dele)
        r, g, b = cor_da_base(cor)
        cores = [] if base in BASES_SEM_COR_DA_LUZ else [f"{r:02X}{g:02X}{b:02X}"]
        efeito = escrever_o_efeito_da_luz(base, cores, RITMO_DA_BASE[base])
    atual = brilho_do_controle(cru, uniq)
    apagada = atual is not None and atual <= 0.0
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    gravar_pelo_gesto(
        "luz", nome,
        lambda prof: _com_o_efeito_gravado(prof, uniq, efeito, religar=efeito is not None),
        uniq=uniq, origem="interface-nova")
    if pedido == SEM_EFEITO:
        _escrever_a_cor(ctx, p, uniq, (0, 0, 0), apagando=True, brilho=0.0)
    elif pedido == LUZ_FIXA and apagada and dele is not None:
        _escrever_a_cor(ctx, p, uniq, _a_cor_de_agora(ctx, cru, dele), escolha=True)
    return None


@gesto("04-iluminacao.html", GESTO_DE_CRIAR_EFEITO, grava="guardar_meus_efeitos")
def criar_efeito_da_luz(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Guarda um efeito novo: a base (um dos cinco do «Jeito»), as cores, o ritmo e o nome.

    Só a caixa de preferências da interface é gravada: nenhum perfil e nenhum aparelho. O efeito
    entra como chip em «Criar efeitos novos» e na lista «Efeito» de cada coluna.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        BASES_DA_LUZ,
        RITMO_MAXIMO_DA_LUZ,
        RITMO_MINIMO_DA_LUZ,
        TETO_DE_CORES_DO_EFEITO,
    )

    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError("não consegui ler a área de criar efeitos. Nada foi guardado.")
    base = str(forma.get("base") or "").strip()
    if base not in BASES_DA_LUZ:
        raise RuntimeError("Escolha como a luz se move: respirar, piscar, arco-íris, onda ou relâmpago.")  # noqa: E501
    cores = [c.strip().upper() for c in str(forma.get("cores") or "").split(",") if c.strip()]
    if not all(re.fullmatch(r"#[0-9A-F]{6}", c) for c in cores):
        raise RuntimeError("Alguma cor do efeito não é válida. Nada foi guardado.")
    if base == "arco-iris":  # (noqa-acento) chave do contrato
        cores = []
    elif not cores:
        raise RuntimeError("Escolha ao menos uma cor para o efeito.")
    if len(cores) > TETO_DE_CORES_DO_EFEITO:
        raise RuntimeError(f"O efeito tem no máximo {TETO_DE_CORES_DO_EFEITO} cores.")
    try:
        ritmo = int(str(forma.get("ritmo") or "").strip())
    except ValueError:
        raise RuntimeError("Escolha o ritmo do efeito.") from None
    if not RITMO_MINIMO_DA_LUZ <= ritmo <= RITMO_MAXIMO_DA_LUZ:
        raise RuntimeError(
            f"O ritmo vai de {RITMO_MINIMO_DA_LUZ} a {RITMO_MAXIMO_DA_LUZ}.")
    apelido = str(forma.get("nome") or "").strip()
    if not apelido:
        raise RuntimeError("Dê um nome ao efeito.")
    if len(apelido) > TETO_DO_NOME:
        raise RuntimeError(f"O nome do efeito tem no máximo {TETO_DO_NOME} letras.")
    todos = meus_efeitos("luz")
    todos[apelido] = {"nome": apelido, "base": base,
                      "parametros": {"cores": ",".join(cores), "ritmo": ritmo}}
    guardar_meus_efeitos(todos, "luz")


_RECONCILIAR_O_COOP = "coop.sync"


def _pares_da_troca(ctx: Contexto, uniq: str, n: int) -> list[tuple[str, int]]:
    """Quem fica com que número DEPOIS da troca — o alvo e o parceiro dele.

    `identity.number.set` **PERMUTA**: o alvo vai para o número pedido, quem o tinha fica com o do
    alvo e mais ninguém se mexe (daemon `_set_number_locked`; desenho aprovado: *"Os dois trocam, os
    outros não se mexem"*). O parceiro entra porque as cinco lâmpadas de um controle preso num
    override velho ficariam no número que o OUTRO acabou de receber: dois controles com o mesmo
    desenho, a colisão que a numeração única (R-24) mata.

    A conta é daqui porque a resposta não a traz (`changed` existe no daemon, mas
    `ipc_bridge.identity_number_set` reduz a `(ok, motivo)`; ler o `state_full` depois custa uma
    volta e um dublê). RELATADO: uma `identity_number_set_detalhado` que entregue o `changed` é
    `app/ipc_bridge.py`, fora deste arquivo. Números saem de `_numero` (dono único,
    `app/actions/base`, o que pinta a fileira). Sem parceiro (número livre) a lista tem um par só.
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

    Queixa de 04/09/2026: *"escolha do jogador no iluminação não funciona"*. O gesto renumerava e
    parava; renumerar não move lâmpada. Medido na bancada (dois DualSense, daemon vivo,
    `/sys/class/leds` a cada passo):

        estado de partida            slot=2 → lâmpadas do 2 · slot=1 → do 1
        1. identity.number.set       slot=1 → lâmpadas do 2 · slot=2 → do 1   ✗
        2. + led.player_set por uniq slot=1 → lâmpadas do 2 · slot=2 → do 1   ✗
        3. + coop.sync               slot=1 → lâmpadas do 1 · slot=2 → do 2   ✓

    A linha 2 é o achado: o daemon respondeu `{"status":"ok","aplicado_em":["<o
    controle>"],"guardado_em":[]}` às duas escritas e nenhuma lâmpada se mexeu. A camada do co-op
    repintou por cima, porque no merge por campo (`backend_pydualsense._merged_desired_for_key`) ela
    está ACIMA do override por-uniq: default global < AUTOMÁTICA < override por-uniq < CO-OP < jogo.
    Ler `aplicado_em` como sucesso poria "aplicado" sobre duas lâmpadas paradas (a mentira da
    MESA-CHEIA-09 na janela GTK).

    Por que a camada do co-op fica velha: é um mapa PUBLICADO (`coop._apply_coop_player_leds`
    calcula `numeros_de_jogador()`, do mesmo `identity_registry`, e publica em
    `_desired_coop_by_uniq`) e só roda no fim de um ciclo CHEIO do co-op, que pede `/dev/input` ter
    mudado, grab degradado ou `force`; renumerar não é nenhum. O `reassert_resolved_outputs()` do
    handler reafirma a camada VELHA até o próximo hotplug. RELATADO, cura estrutural de uma linha no
    daemon: o `_handle_identity_number_set` já adianta `reassert_resolved_outputs` e
    `_schedule_external_tick` no ramo `changed`; falta `get_coop_manager(daemon).sync(force=True)`
    (ou `_apply_coop_player_leds`), em `daemon/ipc_handlers.py`, fora deste arquivo; com ela o ramo
    daqui vira redundância barata.

    Os dois ramos, cada um com o dono das lâmpadas naquele momento:

    * **o co-op manda** (`o_coop_manda`): quem escreve as luzes é a camada dele e só recalculá-la a
    move. `coop.sync` já existe para isso (*"Não liga nem desliga nada"*, *"reconciliar nunca
    ressuscita o que o jogo suspendeu"*); escrever o override seria escrever debaixo de quem manda;
    * **o co-op não manda**: a camada automática SEGUE o número no `reassert` do handler, a menos
      que um override por-uniq esteja preso acima (o que a janela GTK deixa ao usar "Desenho do PN",
      `lightbar_actions._enviar_player_leds`). O override é reescrito com o padrão do número de
      AGORA, do dono da tabela (`core/led_control.player_led_pattern`, a mesma de `luzinhas`).

    Preço do segundo ramo: um override por-uniq PRENDE as lâmpadas acima da camada automática, e
    depois um controle que saia da mesa não faz os outros reacenderem sozinhos (a GTK paga o mesmo
    desde sempre; nenhum IPC limpa o override, `lightbar.reset` é da barra). Só se paga com o co-op
    fora.

    A ordem é renumerar PRIMEIRO (o padrão é função do número NOVO). Se a renumeração passar e a
    lâmpada não, **a renumeração VALE**: desfazê-la seria outra escrita que também pode falhar, e o
    cartão diz o que houve com as luzes (calar seria o silêncio que esta casa nomeia como a
    mentira).
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

    UMA para os quatro gestos de desenho (`luzes`, `desenho-de`, `reenviar-desenho` e `player`):
    quando a cura conhece a causa, cobre TODOS os chamadores (regra de 05/09); quatro `if frase:`
    copiados divergiriam no gesto em que ninguém repara. `None` é o silêncio de sempre e não é
    ausência de resposta: quem responde é a piscada de 1,5 s do piloto
    (`hefesto_vivo.MS_DA_PISCADA`, decisão `03-Q4`).
    """
    return {"recado": frase} if frase else None


def _o_aviso_dos_n(janela: Any) -> str:
    """A frase do dono para o clique que foi para N controles — "" se N < 2.

    Nenhuma sílaba nasce aqui: o texto é `lightbar_actions._AVISO_MESMO_DESENHO_NOS_QUATRO` (dono
    único desde a L12, 25/08/2026) e a conta é `_quantos_recebem_o_desenho`; a função só junta os
    dois, como o `_msg_do_desenho` no fim dele.

    Compõe de novo, embora a frase do dono já venha com o aviso colado, porque não é o texto que vai
    à tela: é a SONDA de *"este desfecho carrega o aviso dos N?"*, a única pergunta que separa um
    recibo de um aviso. Sem ela, no dia em que o dono parasse de colar o aviso o canal verde
    receberia um recibo comum. `_cobrar_a_frase_do_desenho` confere que a sonda está DENTRO da frase
    antes de devolvê-la.
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

    Nenhum texto nasce deste lado (contrato de `_escrever_a_cor`): quem compõe é
    `lightbar_actions._msg_do_desenho`, o dono ÚNICO da frase das cinco luzes (MESA-CHEIA-09/E3;
    três caminhos da GTK passam por ele), chamado DESLIGADO da instância com o `_Janela` da frase da
    cor (lê o estado por funções de `app/textos_de_aplicacao` via `getattr`; o degrau a mais é
    `_quantos_recebem_o_desenho`, zero nesta aba).

    Os três argumentos de texto são os do gêmeo (`_set_player_leds` da GTK, onde vão os botões
    "Desenho do PN"):
    `descricao` de `_descreve_player_leds`,  # (argumento) noqa-acento
    `feito="atualizado"`, `fazer="atualizar"`; outros fariam duas telas contarem o mesmo evento com
    palavras diferentes.

    A frase feliz é PERGUNTADA, nunca digitada (diferente de `_escrever_a_cor`, onde o par existe
    como constante na GTK): aqui é montada DENTRO do `_msg_do_desenho`, sem nome público, e
    digitá-la seria a segunda escrita (RADAR-01). Pergunta-se ao MESMO método com corpo
    sinteticamente feliz (`aplicado_em` com um destino): *"a frase que saiu é a do caminho feliz?"*
    sem conhecer uma sílaba dela. O corpo não é dublê do daemon (nunca vai ao aparelho nem é lido
    como resposta) e as duas chamadas usam o MESMO `_Janela`, então toda pendência (Modo nativo,
    alvo fora da mesa) vale igual e não some na comparação.

    Só corre com o co-op fora: com ele ligado `_acender_o_numero` volta antes (o ramo do co-op
    responde a mesma frase aos dois corpos e a comparação ficaria cega).

    **Devolve a frase quando ela tem aviso** (ILUMINACAO-O-AVISO-DOS-N-01): o `_msg_do_desenho` cola
    `_AVISO_MESMO_DESENHO_NOS_QUATRO` em **toda** frase com N ≥ 2, a do corpo real e a do feliz, que
    ficam iguais, o `!=` cala e o aviso morria aqui (o clique pegaria N controles sem a tela dizer:
    o "nada na tela avisava" da L12). Quem tem aviso devolve a frase inteira do dono e o chamador a
    manda como `{"recado": …}` (desde 13/09/2026 ao diário da janela, TELA-CALADA-01 e
    FRASES-E-DICAS-01). Sem aviso, `""`: o silêncio de antes.

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

    Não é `identity.renumber` (COMPACTA todos preservando a ordem relativa e mora na aba Início,
    `interface/pacotes/a01_jogar.py:2052`); "este controle é o 2" foi o comando que faltou até
    25/07.

    Devolve `(ok, motivo)` com o motivo já em frase (`_MOTIVOS_NUMERO`); levantar com ele faz o
    botão RECUSAR em vez de falhar calado (desde 13/09/2026, FRASES-E-DICAS-01, o botão pisca a
    recusa e a frase vai ao diário da janela). Era meio gesto até 04/09/2026: o número exibido
    trocava e as cinco lâmpadas não; ver `_acender_o_numero` (inclusive por que escrever o desenho
    por `uniq` não funciona com o co-op ligado).

    :return: `{"recado": …}` quando o desenho pegou em N > 1 controles
    (ILUMINACAO-O-AVISO-DOS-N-01); `None` no resto. **A troca escrever em DOIS controles não é esse
    caso**: cada um recebe o desenho do NÚMERO dele e o aviso do dono fala de um MESMO desenho.
    """
    _nao_no_automatico(ctx)
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




# `lightbar_brightness` de TODOS os overrides por controle e religava


#: A PORTA DA COR É A `_detalhado` DESDE 03/09/2026, e `led_set` saiu daqui: o
PONTE = {"led_set_detalhado", "identity_number_set",
         "player_leds_set_detalhado", "player_led_brightness_set_detalhado",
         "chamar", "profile_switch"}
METODOS = {"coop.sync"}


PAGINA = "04-iluminacao.html"
#: o indicador virou o botão de reenvio (`reenviar-desenho`) e a faixa do título
#: `luzes`, `desenho-de` e `reenviar-desenho` —, e saíram com o widget que os
#: Desceu de 10 para 8 em 16/10/2026, pedido: o «Sem piscar» e a caixa do hexadecimal
#: (`reenviar`) saíram da tela, e o gesto saiu com o widget.
PISO_DA_ABA = 8
PROVAS = [
    {"pagina": PAGINA, "gesto": "cor", "clique": {"hex": "#FF8000"},  # (noqa-acento) id
     "chama": [("led_set_detalhado", [(255, 128, 0)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "apagar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("led_set_detalhado", [(0, 0, 0)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": GESTO_DO_EFEITO,  # (noqa-acento) id
     "clique": {"valor": SEM_EFEITO},
     "chama": [("led_set_detalhado", [(0, 0, 0)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "player", "clique": {"player": "2"},  # (noqa-acento) id
     "chama": [("identity_number_set", ["aa:bb:cc:00:00:01", 2], {}),
               ("player_leds_set_detalhado", [(False, True, False, True, False)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    # Ele provava o `reenviar-desenho`, que era o clique na moldura das cinco
]
