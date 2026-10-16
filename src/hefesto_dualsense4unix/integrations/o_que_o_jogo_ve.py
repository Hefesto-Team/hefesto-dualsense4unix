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

#: A máscara da fábrica e o nome da forma que o estado publica.
FORMAS: Final[dict[str, str]] = {"dualsense": "dualsense", "xbox": "xbox360", "nintendo": "pro"}

FUNCOES: Final[tuple[str, ...]] = (
    "botoes", "analogicos", "gatilho_analogico", "gatilho_adaptativo", "vibracao", "haptica",
    "luz", "luz_de_jogador", "giroscopio", "touchpad", "microfone", "alto_falante",
)

#: O giroscópio e o touchpad saem das escolhas (o perfil e o controle), e não da tabela.
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


def _o_movimento_anda(movimento: object) -> bool:
    """A Mira Virtual leva o giro ou a inclinação deste controle a um analógico ou ao mouse."""
    return bool(getattr(movimento, "ligado", False) or getattr(movimento, "inclina", False))


def o_que_o_jogo_ve(
    vpad: object,
    movimento: object = None,
    *,
    transporte: object = None,
    giro_ligado: bool = True,
    toque_ligado: bool = True,
) -> dict[str, Any] | None:
    """O que o jogo vê deste pad, ou ``None`` quando o pad não sabe dizer.

    ``movimento`` é o arranjo de mira desta peça (`roteador_de_movimento.da_peca`);
    ``transporte`` é o do plástico (`usb` ou `bt`); ``giro_ligado`` e
    ``toque_ligado`` são as chaves por controle (`virtual_motion.REGISTRO`).
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
    if forma == "dualsense":
        funcoes["giroscopio"] = NATIVO if giro_ligado else NAO_CHEGA
        funcoes["touchpad"] = NATIVO if toque_ligado else NAO_CHEGA
    else:
        funcoes["giroscopio"] = PELO_HEFESTO if _o_movimento_anda(movimento) else NAO_CHEGA
        funcoes["touchpad"] = PELO_HEFESTO if toque_ligado else NAO_CHEGA
    return {
        "forma": forma,
        "canal": canal,
        "conexao": _CONEXOES.get(str(transporte)),  # (noqa-acento): a chave ASCII do estado
        "troca_motivo": _texto(getattr(vpad, "troca_motivo", None)),
        "degradado_motivo": degradado,
        "funcoes": {nome: funcoes[nome] for nome in FUNCOES},  # (noqa-acento): idem
    }


__all__ = [
    "FORMAS",
    "FUNCOES",
    "NAO_CHEGA",
    "NATIVO",
    "PELO_HEFESTO",
    "o_que_o_jogo_ve",
]
