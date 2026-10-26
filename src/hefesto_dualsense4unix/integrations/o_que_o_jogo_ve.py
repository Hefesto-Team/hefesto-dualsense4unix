"""O que o jogo vê de UM pad virtual: a forma, o canal e o que chega de cada função.

A forma sai da regra da fábrica (`virtual_pad.mascara_no_jogo`), nunca de uma
segunda; a tabela das doze funções é a medida de 13/10 (a máscara com três
alvos). `nativo` = o jogo fala com a função; `pelo_hefesto` = chega convertida
(o rumble que vira háptica, a Mira Virtual, o gatilho e a luz do perfil, o
touchpad como mouse do PC, o microfone e o alto-falante do PC); `nao_chega` =
a forma não tem o canal. Puro: nada toca o aparelho, e nada levanta.
"""

from __future__ import annotations

from typing import Any, Final

from hefesto_dualsense4unix.integrations import virtual_pad

NATIVO: Final = "nativo"
PELO_HEFESTO: Final = "pelo_hefesto"
NAO_CHEGA: Final = "nao_chega"

FORMAS: Final[dict[str, str]] = {"dualsense": "dualsense", "xbox": "xbox360", "nintendo": "pro"}

FUNCOES: Final[tuple[str, ...]] = (
    "botoes", "analogicos", "gatilho_analogico", "gatilho_adaptativo", "vibracao", "haptica",
    "luz", "luz_de_jogador", "giroscopio", "touchpad", "microfone", "alto_falante",
)

_TABELA: Final[dict[str, dict[str, str]]] = {
    "dualsense": dict.fromkeys(FUNCOES, NATIVO),
    "xbox360": {
        "botoes": NATIVO, "analogicos": NATIVO, "gatilho_analogico": NATIVO,
        "gatilho_adaptativo": PELO_HEFESTO, "vibracao": NATIVO, "haptica": PELO_HEFESTO,
        "luz": PELO_HEFESTO, "luz_de_jogador": PELO_HEFESTO,
        "microfone": PELO_HEFESTO, "alto_falante": PELO_HEFESTO,
    },
    "pro": {
        "botoes": NATIVO, "analogicos": NATIVO, "gatilho_analogico": NAO_CHEGA,
        "gatilho_adaptativo": PELO_HEFESTO, "vibracao": NATIVO, "haptica": PELO_HEFESTO,
        "luz": PELO_HEFESTO, "luz_de_jogador": NAO_CHEGA,
        "microfone": PELO_HEFESTO, "alto_falante": PELO_HEFESTO,
    },
}

_CONEXOES: Final[dict[str, str]] = {"usb": "cabo", "bt": "radio"}


def _texto(valor: object) -> str | None:
    return valor if isinstance(valor, str) and valor else None


def _o_giro(forma: str, movimento: object, *, giro_ligado: bool, acel_ligado: bool) -> str:
    """O giroscópio, pelas mesmas portas do tique (`gamepad.aplicar_o_movimento`).

    A Mira anda só com o sensor ligado; no DualSense, a Mira que anda tira o giro
    do relatório do pad (`virtual_motion.REGISTRO.filtrar`), e o jogo o recebe convertido.
    """
    mira = bool(getattr(movimento, "ligado", False)) and giro_ligado
    if forma == "dualsense":
        if mira:
            return PELO_HEFESTO
        return NATIVO if giro_ligado else NAO_CHEGA
    inclina = bool(getattr(movimento, "inclina", False)) and acel_ligado
    return PELO_HEFESTO if mira or inclina else NAO_CHEGA


def _o_toque(forma: str, movimento: object, *, toque_ligado: bool) -> str:
    """O touchpad: o dedo que vai ao cursor ou às zonas sai do relatório do pad."""
    if not toque_ligado:
        return NAO_CHEGA
    if forma == "dualsense" and not getattr(movimento, "toca", False):
        return NATIVO
    return PELO_HEFESTO


def _a_porta(vpad: object) -> str | None:
    """Por que o pad DualSense está sem a porta USB própria; None = tem, ou não sabe dizer.

    A háptica do jogo é áudio do controle, e o jogo acha o áudio pelo pai USB
    do pad: sem a porta, a háptica não é nativa, e chega só o rumble que o
    Hefesto converte. O motivo é o que o pad anotou (`pad_usb.anotar_sem_porta`).
    """
    motivo = getattr(vpad, "porta_motivo", None)
    return motivo if isinstance(motivo, str) and motivo else None


def o_que_o_jogo_ve(
    vpad: object,
    movimento: object = None,
    *,
    transporte: object = None,
    giro_ligado: bool = True,
    acel_ligado: bool = True,
    toque_ligado: bool = True,
) -> dict[str, Any] | None:
    """O que o jogo vê deste pad, ou ``None`` quando o pad não sabe dizer.

    ``movimento`` é o arranjo de mira desta peça (`roteador_de_movimento.da_peca`);
    ``transporte`` é o do plástico (`usb` ou `bt`); ``giro_ligado``,
    ``acel_ligado`` e ``toque_ligado`` são as chaves por controle
    (`virtual_motion.REGISTRO`).
    """
    mascara = _texto(getattr(vpad, "flavor", None))
    canal = _texto(getattr(vpad, "backend", None))
    if mascara not in FORMAS or canal not in ("uhid", "uinput"):
        return None
    degradado = virtual_pad.motivo_da_degradacao(vpad)
    aparelho = virtual_pad.mascara_no_jogo(
        virtual_pad.caminho_do_vpad(vpad), mascara, sem_canal=degradado is not None
    )
    forma = FORMAS.get(aparelho)
    if forma is None:
        return None
    funcoes = dict(_TABELA[forma])
    funcoes["giroscopio"] = _o_giro(
        forma, movimento, giro_ligado=giro_ligado, acel_ligado=acel_ligado
    )
    funcoes["touchpad"] = _o_toque(forma, movimento, toque_ligado=toque_ligado)
    porta = _a_porta(vpad) if forma == "dualsense" else None
    if porta is not None:
        funcoes["haptica"] = PELO_HEFESTO
    return {
        "forma": forma,
        "canal": canal,
        "conexao": _CONEXOES.get(str(transporte)),  # (noqa-acento)
        "troca_motivo": _texto(getattr(vpad, "troca_motivo", None)),
        "degradado_motivo": degradado,
        "porta_motivo": porta,
        "funcoes": {nome: funcoes[nome] for nome in FUNCOES},  # (noqa-acento)
    }


__all__ = [
    "FORMAS",
    "FUNCOES",
    "NAO_CHEGA",
    "NATIVO",
    "PELO_HEFESTO",
    "o_que_o_jogo_ve",
]
