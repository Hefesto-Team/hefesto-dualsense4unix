"""Controles externos (não-DualSense) na GUI — 8BIT-02.

Lógica PURA (testável sem GTK) para a superfície read-only dos controles que o
Hefesto VÊ mas NÃO adota (8BitDo, Nintendo, Xbox, etc.). Consome o inventário
do IPC ``controller.list {external: true}`` (8BIT-01): cada entrada tem
``name, vid, pid, bus, uniq, driver, evdev_path, hidraw, identity,
player_slot`` e, opcionalmente, ``holders``.

Regra de ouro desta frente (escopo ditado pela mantenedora): "só uma aba pra
ver como os controles aparecem, não uma super central". Aqui NÃO se controla
nada — só se traduz a identidade crua para linguagem de gente e se avisa a
armadilha conhecida (o Nintendo/8BitDo por Bluetooth morre — é o driver
``hid-nintendo`` do kernel desistindo, NÃO o Hefesto).

**NOTA DATADA — 21/08/2026: o escopo acima foi REABERTO por ela.** A ``D-A2`` de
``docs/process/sprints/2026-08-21-ABA-CONFIGURACOES/DECISOES-ABERTAS.md`` foi
respondida mantendo a seção "Os controles" na leva da aba Configurações —
**contrária à recomendação**, que era cortá-la justamente por causa da fala
acima. A escolha é dela e está registrada com data; a fala de origem fica onde
está, porque decisão revogada nesta casa ganha uma segunda data, nunca some.

O que a reabertura acrescenta a este arquivo, e só isso: as funções puras que a
seção consome (:func:`modo_deduzido`, :func:`declaracoes_do_aparelho`,
:func:`cores_do_plastico_items`). Continua sem controlar nada — o único gesto
que sai desta seção para o aparelho é o número de jogador, que já existia de
ponta a ponta, e as declarações, que vão para o ``maquina.json`` e não para o
firmware de ninguém.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.core.linhagem_nintendo import OUIS_CLONE

_IDENTITY_FIELD = "identity"

_TYPE_BY_VIDPID: dict[str, str] = {
    "057e:2009": "Pro Controller (modo Switch)",
    "057e:2017": "Pro Controller (modo Switch)",
    "057e:2006": "Joy-Con (E)",
    "057e:2007": "Joy-Con (D)",
    "045e:028e": "Xbox 360",
    "045e:02ea": "Xbox One",
    "045e:02fd": "Xbox One (Bluetooth)",
    "045e:0b12": "Xbox Series",
    "045e:0b13": "Xbox Series (Bluetooth)",
    "28de:1142": "Steam Controller",
}

_VENDOR_BY_VID: dict[str, str] = {
    "057e": "Nintendo",
    "045e": "Xbox",
    "2dc8": "8BitDo",
    "0f0d": "HORI",
    "20d6": "PowerA",
    "28de": "Valve",
    "054c": "Sony",  # não deveria chegar aqui (o inventário exclui DualSense)
}

_NINTENDO_MODE_VIDS = frozenset({"057e"})

_BRAND_BY_OUI: dict[str, str] = dict.fromkeys(OUIS_CLONE, "8BitDo")


def _vidpid(entry: dict[str, Any]) -> str:
    vid = str(entry.get("vid") or "").lower()
    pid = str(entry.get("pid") or "").lower()
    return f"{vid}:{pid}"


def _oui_of(entry: dict[str, Any]) -> str | None:
    """OUI (6 hex minúsculos) do MAC do controle, ou ``None`` sem ``uniq``."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    uniq = entry.get("uniq")
    mac = norm_mac(uniq if isinstance(uniq, str) else None)
    return mac[:6] if mac and len(mac) >= 6 else None


def friendly_type(entry: dict[str, Any]) -> str:
    """Tipo amigável do controle externo (ex.: 'Pro Controller (modo Switch)')."""
    vp = _vidpid(entry)
    if vp in _TYPE_BY_VIDPID:
        return _TYPE_BY_VIDPID[vp]
    oui = _oui_of(entry)
    if oui and oui in _BRAND_BY_OUI:
        return _BRAND_BY_OUI[oui]
    vid = str(entry.get("vid") or "").lower()
    vendor = _VENDOR_BY_VID.get(vid)
    if vendor:
        return vendor
    name = str(entry.get("name") or "").strip()
    return name or "Controle externo"


def brand_of(entry: dict[str, Any]) -> str:
    """Marca do controle, com o OUI do MAC VENCENDO o VID."""
    oui = _oui_of(entry)
    if oui and oui in _BRAND_BY_OUI:
        return _BRAND_BY_OUI[oui]
    vid = str(entry.get("vid") or "").lower()
    return _VENDOR_BY_VID.get(vid) or friendly_type(entry)


def transport_label(entry: dict[str, Any]) -> str:
    """'Cabo (USB)' | 'Bluetooth' | o valor cru quando desconhecido."""
    bus = str(entry.get("bus") or "").lower()
    if bus == "usb":
        return "Cabo (USB)"
    if bus in ("bluetooth", "bt"):
        return "Bluetooth"
    return bus or "desconhecido"


def external_slot(dualsense_count: int, index: int) -> int:
    """Slot GLOBAL de co-op de um externo: continua a numeração dos DualSense.

    Com 2 DualSense (slots 1 e 2), o 1º externo é o Controle 3, o 2º é o 4 —
    o MESMO número que o Hefesto escreve no LED de player do controle, para a
    GUI e o LED nunca discordarem. ``index`` é 0-based na lista de externos.
    """
    return dualsense_count + index + 1


def slot_of(entry: dict[str, Any], dualsense_count: int, index: int) -> int | None:
    """Slot do externo: o `player_slot` que o DAEMON já mandou (fonte única —
    é o MESMO que ele escreveu no LED), com fallback para o cálculo local
    SÓ em daemons antigos que nem sequer expõem o campo.

    NUMA-05: a chave `player_slot` PRESENTE (ainda que valendo ``None`` — o
    registry sem opinião ainda) é a fonte única e vence SEMPRE — devolve
    ``None`` sem calcular nada. O posicional `external_slot` (que
    reembaralhava a numeração a cada troca de `dualsense_count` — o ponto
    cego do incidente de 14:42) só roda quando a CHAVE está AUSENTE (daemon
    de antes do 8BIT-02, que nunca mandou `player_slot`). Null honesto
    (exibido como "—" via :func:`slot_label`) vale mais que número errado.
    """
    if "player_slot" in entry:
        slot = entry["player_slot"]
        if isinstance(slot, int) and not isinstance(slot, bool) and slot >= 1:
            return slot
        return None
    return external_slot(dualsense_count, index)


def slot_label(slot: int | None) -> str:
    """Texto de exibição do slot: o número, ou "—" honesto (NUMA-05).

    Centraliza a regra "null > número errado" num único ponto — a GUI nunca
    mais inventa um número quando o registry ainda não opinou.
    """
    return str(slot) if slot is not None else "—"


def button_labels_for(
    externals: list[dict[str, Any]], dualsense_count: int = 0
) -> list[str]:
    """Rótulos dos botões dos externos, numerados pelo SLOT GLOBAL de co-op.

    Continua a contagem dos DualSense (``dualsense_count``): com 2 DualSense,
    os externos viram "Nintendo 3 · cabo", "Nintendo 4 · cabo" — SINCRONIZADO
    com o número que aparece no LED de player do próprio controle. Ordem = a
    do inventário (estável por ``uniq`` no backend).
    """
    saida: list[str] = []
    for i, e in enumerate(externals):
        slot = slot_of(e, dualsense_count, i)
        nome = brand_of(e)
        bus = str(e.get("bus") or "").lower()
        via = "cabo" if bus == "usb" else ("BT" if bus in ("bluetooth", "bt") else bus)
        if slot is None:
            saida.append(f"{nome} · {via}" if via else nome)
        else:
            saida.append(f"{nome} {slot} · {via}" if via else f"{nome} {slot}")
    return saida


def nintendo_bt_warning(entry: dict[str, Any]) -> str | None:
    """Aviso honesto quando é um controle Nintendo-mode POR Bluetooth."""
    vid = str(entry.get("vid") or "").lower()
    bus = str(entry.get("bus") or "").lower()
    if vid in _NINTENDO_MODE_VIDS and bus in ("bluetooth", "bt"):
        return (
            "Pelo BT o modo Switch pode travar (driver do kernel); "
            "pelo USB é estável."
        )
    return None


MODOS_DO_APARELHO: list[tuple[str, str]] = [
    ("dinput", "D-input"),
    ("xinput", "X-input"),
    ("switch", "Switch"),
    ("macos", "Apple"),
]

_MODO_LEGADO: dict[str, str] = {"switch": "nintendo", "xinput": "xbox"}


def modo_deduzido(entry: dict[str, Any]) -> str:
    """O modo de hardware em que o controle foi ligado, DEDUZIDO. "" = não sei.

    Decisão T1: o modo é deduzido e MOSTRADO, nunca declarado. A dedução tem
    grau ALTA em cinco dos sete pares modo-transporte
    (``externos-firmware-e-modos.md:218-228``), e declará-lo colidiria com a
    salvaguarda 2 da ``D-A1`` ("onde a medição existe, ela pré-preenche e a
    declaração só corrige") — além de nascer órfã: o MAC do 8BitDo MUDA com o
    modo (``docs/usage/troubleshooting-8bitdo.md:27-29``), então uma
    declaração gravada por identidade descreve um aparelho que não existe mais
    no instante em que a pessoa troca o modo que ela descrevia.

    A tabela de dedução é a da canônica (``:145-149``), e a ordem das perguntas
    aqui é a ordem de sempre — Switch antes de X-input — para o retorno legado
    de :func:`input_mode` continuar byte a byte o que era:

    ============  ==================  ==================  ==================
    modo          VID:PID no cabo     VID:PID no rádio    driver no Linux
    ============  ==================  ==================  ==================
    D-input       ``2dc8:6001/6002``  ``2dc8:6101/6102``  ``hid-generic``
    X-input       ``045e:028e``       ``045e:02e0``       ``xpad``/microsoft
    macOS/Apple   ``054c:05c4``       ``054c:05c4``       ``hid-playstation``
    Switch        ``057e:2009``       ``057e:2009``       ``hid-nintendo``
    ============  ==================  ==================  ==================

    O ``""`` é resposta legítima e vai à tela como "Não sei": um controle que
    não é dessa família não tem modo nenhum a mostrar, e chutar um seria a tela
    afirmando o que ninguém mediu.
    """
    vid = str(entry.get("vid") or "").lower()
    driver = str(entry.get("driver") or "").lower()
    if vid == "057e" or driver in ("nintendo", "hid-nintendo"):
        return "switch"
    if vid == "045e" or driver in ("xpad", "microsoft", "hid-microsoft"):
        return "xinput"
    if vid == "2dc8":
        return "dinput"
    if vid == "054c" or driver in ("playstation", "hid-playstation"):
        # O inventário de externos EXCLUI o DualSense adotado, então um VID da
        return "macos"
    return ""


def input_mode(entry: dict[str, Any]) -> str:
    """Modo do controle: 'nintendo' (Switch), 'xbox' (X-input) ou 'outro'."""
    return _MODO_LEGADO.get(modo_deduzido(entry), "outro")


MODE_SELECTOR_ITEMS: list[tuple[str, str]] = [
    ("nintendo", "Nintendo (Switch)"),
    ("xbox", "Xbox (X-input)"),
]

MODE_SELECTOR_SUBTITLE = (
    "O modo é uma troca física no controle (combo ao ligar) — veja o manual."
)

MODE_SELECTOR_TOOLTIP = (
    "Só leitura: mostra o modo em que o controle está agora. A troca não é "
    "por software — é um combo de botões no próprio controle ao ligar."
)


def mode_selector_state(
    entry: dict[str, Any],
) -> tuple[list[tuple[str, str]], str] | None:
    """(itens, id ativo) do segmentado read-only da ficha — ou ``None``."""
    modo = input_mode(entry)
    if modo not in ("nintendo", "xbox"):
        return None
    return list(MODE_SELECTOR_ITEMS), modo


def mode_guidance(entry: dict[str, Any]) -> tuple[str, str] | None:
    """(modo_atual_legível, orientação) para a ficha — ou None se não se aplica."""
    modo = input_mode(entry)
    if modo == "nintendo":
        atual = "Nintendo (modo Switch)"
        orient = "Switch: tem giroscópio. Xbox (X-input): mais estável, sem giroscópio."
        return atual, orient
    if modo == "xbox":
        atual = "Xbox (X-input)"
        orient = "Xbox (X-input): mais estável, sem giroscópio. Switch: tem giroscópio."
        return atual, orient
    return None


def detail_rows(entry: dict[str, Any]) -> list[tuple[str, str]]:
    """Linhas ``(rótulo, valor)`` da ficha read-only do controle externo."""
    rows: list[tuple[str, str]] = [
        ("Controle", friendly_type(entry)),
        ("Como conectou", transport_label(entry)),
    ]
    driver = str(entry.get("driver") or "").strip()
    if driver:
        rows.append(("Driver do Linux", driver))
    nome = str(entry.get("name") or "").strip()
    if nome and nome != friendly_type(entry):
        rows.append(("Nome do sistema", nome))
    rows.append(("Gerenciado por", "Linux + Steam (o Hefesto não mexe nele)"))
    return rows


def external_key(entry: dict[str, Any]) -> str:
    """Chave estável do controle externo — o `identity` que o daemon carimbou."""
    identity = entry.get(_IDENTITY_FIELD)
    if isinstance(identity, str) and identity:
        return identity
    uniq = entry.get("uniq")
    if isinstance(uniq, str) and uniq:
        return uniq
    return str(entry.get("evdev_path") or entry.get("hidraw") or entry.get("name") or "?")


#: arbitrário: ``00``-``05`` são as cores de catálogo do DualSense, e as outras
_CORES_DA_LISTA: tuple[tuple[str, str], ...] = (
    ("00", "Branco"),
    ("01", "Preto"),
    ("02", "Vermelho"),
    ("03", "Rosa"),
    ("04", "Roxo"),
    ("05", "Azul"),
)

ID_DE_OUTRA_COR = "outra"

DICA_DE_OUTRA_COR = "Para um modelo fora da lista, ou uma edição especial."

ID_DE_NAO_SEI = "nao_sei"

DICA_DE_NAO_SEI = "Apaga o que foi declarado aqui. O Hefesto volta a não saber."

#: Os códigos que a Sony vende no catálogo corrente do DualSense. São os seis
_CODIGOS_DE_CATALOGO = frozenset(
    {"00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"}
)

DICA_DE_CATALOGO = "Cor de catálogo do DualSense."
DICA_DE_EDICAO = "Edição especial ou coleção."


def cores_do_plastico_items() -> list[tuple[str, str]]:
    """``(id, rótulo)`` da lista de cor — seis nomes, "Outra" e "Não sei"."""
    return [*_CORES_DA_LISTA, (ID_DE_OUTRA_COR, "Outra"), (ID_DE_NAO_SEI, "Não sei")]


def cores_para_busca() -> list[tuple[str, str]]:
    """``(id, nome)`` de TODAS as cores de fábrica, mais "Outra" e "Não sei"."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import NOMES_DE_FABRICA

    return [
        *NOMES_DE_FABRICA.items(),
        (ID_DE_OUTRA_COR, "Outra"),
        (ID_DE_NAO_SEI, "Não sei"),
    ]


def sinonimos_da_busca() -> dict[str, str]:
    """``{código: palavra em português}`` — o que também ACHA, sem se mostrar."""
    return {
        ident: rotulo
        for ident, rotulo in cores_do_plastico_items()
        if ident not in (ID_DE_OUTRA_COR, ID_DE_NAO_SEI)
    }


def dicas_da_busca() -> dict[str, str]:
    """``{id: dica}`` da busca de cor — a dica é a FAMÍLIA da cor."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import NOMES_DE_FABRICA

    dicas = {
        codigo: (
            DICA_DE_CATALOGO if codigo in _CODIGOS_DE_CATALOGO else DICA_DE_EDICAO
        )
        for codigo in NOMES_DE_FABRICA
    }
    das_cores = dicas_das_cores()
    dicas[ID_DE_OUTRA_COR] = das_cores[ID_DE_OUTRA_COR]
    dicas[ID_DE_NAO_SEI] = das_cores[ID_DE_NAO_SEI]
    return dicas


def dicas_das_cores() -> dict[str, str]:
    """``{id: dica}`` da lista de cor — o nome OFICIAL de fábrica, em inglês."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import NOMES_DE_FABRICA

    dicas = {codigo: NOMES_DE_FABRICA[codigo] for codigo, _ in _CORES_DA_LISTA}
    dicas[ID_DE_OUTRA_COR] = DICA_DE_OUTRA_COR
    dicas[ID_DE_NAO_SEI] = DICA_DE_NAO_SEI
    return dicas


def nome_oficial_da_cor(codigo: str) -> str | None:
    """O nome de fábrica de um id da lista, ou ``None`` para "Outra"/desconhecido."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import cor_do_codigo

    cor = cor_do_codigo(codigo)
    return None if cor is None else cor.nome


_CAMPOS_DECLARAVEIS: tuple[tuple[str, str], ...] = (
    ("botoes", "Botões:"),
    ("cor", "Cor:"),
)


def declaracoes_do_aparelho(
    entry: dict[str, Any],
    *,
    adotado: bool = False,
    declarado: Any = None,
) -> list[tuple[str, str, str | None]]:
    """``(chave, rótulo, valor declarado)`` de cada campo que o card pergunta.

    **Todo valor nasce ``None``, e ``None`` é a resposta "não sei".** Não há
    default de catálogo em lugar nenhum desta função, e a ausência é o ponto: o
    editor de perfis já pagou por um default silencioso — o ``or "xbox"`` de
    ``daemon/subsystems/external_mask.py:143-149`` apagava giroscópio e touchpad
    de quem nunca pediu nada. Um valor chutado aqui é pior que campo vazio,
    porque parece informação.

    ``adotado`` diz se é um controle que o Hefesto adotou (DualSense). Ele pede
    só a cor: o rótulo dos botões é pergunta de aparelho que tem dois desenhos
    possíveis, e o DualSense tem um só. O discriminador é argumento e não
    palpite sobre o VID porque o VID MENTE — um 8BitDo em modo macOS reporta
    ``054c`` (Sony), e é exatamente o card dele que mais precisa das duas linhas.

    ``declarado`` é o ``ControleDeclarado`` do ``maquina.json`` (ou qualquer
    objeto com os mesmos atributos, ou um dicionário). Ausente = nada declarado.
    """
    campos = _CAMPOS_DECLARAVEIS[1:] if adotado else _CAMPOS_DECLARAVEIS
    return [
        (chave, rotulo, _valor_declarado(declarado, chave)) for chave, rotulo in campos
    ]


def _valor_declarado(declarado: Any, chave: str) -> str | None:
    """O valor de ``chave`` na declaração, ou ``None`` — nunca levanta."""
    if declarado is None:
        return None
    valor = (
        declarado.get(chave)
        if isinstance(declarado, dict)
        else getattr(declarado, chave, None)
    )
    return valor if isinstance(valor, str) and valor else None


def via_do_controle(entry: dict[str, Any]) -> str:
    """Como o controle chegou, na palavra do desenho: "cabo" ou "Bluetooth"."""
    bus = str(entry.get("bus") or "").lower()
    if bus == "usb":
        return "cabo"
    if bus in ("bluetooth", "bt"):
        return "Bluetooth"
    return bus


def marca_e_via(entry: dict[str, Any], *, marca: str | None = None) -> str:
    """O subtítulo do card: "Sony · cabo", "8BitDo · Bluetooth".

    ``marca`` vem preenchida para o controle adotado — ali a marca não se deduz,
    se sabe: o inventário do daemon só adota DualSense. Para os externos ela sai
    de :func:`brand_of`, que faz o OUI do MAC vencer o VID.

    O separador é o ponto-médio U+00B7, o mesmo do resto da janela.
    """
    nome = marca if marca else brand_of(entry)
    via = via_do_controle(entry)
    return f"{nome} · {via}" if via else nome


def chave_de_maquina(entry: dict[str, Any]) -> str | None:
    """A chave deste controle no ``maquina.json``, ou ``None`` se não há uma."""
    bruto = external_key(entry) if entry.get(_IDENTITY_FIELD) else entry.get("uniq")
    if not isinstance(bruto, str):
        return None
    limpo = bruto.replace(":", "").replace("-", "").strip().lower()
    if len(limpo) != 12 or any(caractere not in "0123456789abcdef" for caractere in limpo):
        return None
    if limpo.startswith("02"):
        return None
    return limpo
