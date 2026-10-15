"""Efeitos de imersão: três por acionamento, com variante por estilo de jogo.

Cada um ajusta o modo que já está aceso, dentro das faixas do `PRESETS`, e nunca
troca o modo; «Nenhum» volta aos padrões. `ajustes` e `variantes` (`{modo: {nome:
valor}}`) são aplicados pela aba Gatilhos; `momentos` (o que muda com o tempo de
aperto) são tocados pelo motor do tato (`tato_vivo.AtuadorDosMomentos`), onde o jogo
cala o gatilho. A imersão se reconhece pelos números (:func:`imersao_dos_numeros`),
a mesma regra na tela e no motor. A régua `test_a_aba_gatilhos_do_todo.py` prende
faixas, teto de escritas, unicidade e a dica: só diz o tempo a imersão que o motor
toca em todo modo dela. Fontes e grau: nota de 12/10 da sprint `A-ABA-GATILHOS-DO-TODO-01`.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field

#: acionamento (família de modos) → os modos que a compõem
FAMILIAS: dict[str, tuple[str, ...]] = {
    "arma": ("SemiAutoGun", "Weapon"),
    "metralhadora": ("Machine", "AutoGun", "Vibration"),
    "arco": ("Bow",),
    "resistência": ("Resistance", "Rigid", "SimpleRigid", "Feedback"),
    "galope": ("Galloping",),
    "pulso": ("PulseA", "PulseB"),
}

Ajustes = Mapping[str, int]


@dataclass(frozen=True)
class Momento:
    """Uma mudança no tempo: `quando` (ao apertar, segurando, sempre) + `apos_ms`."""

    quando: str
    apos_ms: int
    modo: str
    ajustes: Ajustes
    dura_ms: int | None = None
    a_cada_ms: int | None = None
    #: os modos do acionamento em que ele vale; vazio vale em todos
    valem_em: tuple[str, ...] = ()


@dataclass(frozen=True)
class Imersao:
    chave: str
    rotulo: str
    familia: str
    #: a frase da dica da opção (o que se sente), sem «?» na tela
    dica: str
    ajustes: Mapping[str, Ajustes]
    #: estilo (`estilos_de_jogo.Estilo.chave`) → ajustes que SOBREPÕEM os de `ajustes`
    variantes: Mapping[str, Mapping[str, Ajustes]] = field(default_factory=dict)
    momentos: tuple[Momento, ...] = ()
    #: os estilos que a põem no começo da lista com o automático ligado
    na_frente: tuple[str, ...] = ()
    #: nome ainda sem a palavra de produto
    a_validar: bool = False


def _rampa(modo: str, nome: str, de: int, ate: int, cada_ms: int, *,
           valem_em: tuple[str, ...] = (), quando: str = "segurando") -> tuple[Momento, ...]:
    """A subida de um ajuste, degrau por degrau, um por `cada_ms`."""
    passo = 1 if ate >= de else -1
    return tuple(
        Momento(quando, i * cada_ms, modo, {nome: valor}, valem_em=valem_em)
        for i, valor in enumerate(range(de + passo, ate + passo, passo), start=1))


IMERSOES: tuple[Imersao, ...] = (
    # --- Arma: SemiAutoGun e Weapon -------------------------------------------------
    Imersao("ferrolho-que-volta", "Ferrolho que volta", "arma",
            "O gatilho rearma sozinho a cada tiro, firme e curto.",
            {"SemiAutoGun": {"start": 3, "end": 7, "force": 6},
             "Weapon": {"start": 2, "end": 6, "force": 210}},
            na_frente=("fps", "acao", "luta")),  # (noqa-acento): chave
    Imersao("trava-seca", "Trava seca", "arma",
            "Pouco curso e muita resistência, como arma sem munição.",
            {"SemiAutoGun": {"start": 2, "end": 3, "force": 8},
             "Weapon": {"start": 0, "end": 1, "force": 255}},
            na_frente=("fps", "acao")),  # (noqa-acento): chave
    Imersao("pino-que-falha", "Pino que falha", "arma",
            "O disparo fica fundo e duro, e emperra meio segundo a cada aperto.",
            {"SemiAutoGun": {"start": 4, "end": 6, "force": 7},
             "Weapon": {"start": 3, "end": 7, "force": 230}},
            momentos=(Momento("ao_apertar", 0, "Feedback",
                              {"position": 5, "strength": 8}, dura_ms=500),),
            na_frente=("terror",)),
    # --- Metralhadora: Machine, AutoGun e Vibration ---------------------------------
    Imersao("rajada-que-sobe-sozinha", "Rajada que sobe sozinha", "metralhadora",
            "Batidas médias em ritmo constante enquanto você segura.",
            {"Machine": {"start": 0, "end": 9, "strength": 5, "frequency": 8},
             "AutoGun": {"start": 1, "strength": 7, "frequency": 16},
             "Vibration": {"position": 0, "amplitude": 5, "frequency": 8}},
            {"fps": {"AutoGun": {"start": 1, "strength": 7, "frequency": 60},
                     "Machine": {"start": 0, "end": 9, "strength": 5, "frequency": 24}}},
            (Momento("segurando", 0, "Machine", {"strength": 7}, a_cada_ms=200,
                     valem_em=("Machine",)),),
            na_frente=("fps", "acao")),  # (noqa-acento): chave
    Imersao("cano-que-esquenta", "Cano que esquenta", "metralhadora",
            "Batidas rápidas e fortes enquanto você segura.",
            {"Machine": {"start": 0, "end": 9, "strength": 6, "frequency": 20},
             "AutoGun": {"start": 1, "strength": 6, "frequency": 20},
             "Vibration": {"position": 0, "amplitude": 6, "frequency": 20}},
            momentos=(Momento("segurando", 3000, "Machine", {"frequency": 8},
                              valem_em=("Machine",)),
                      Momento("segurando", 3000, "Vibration", {"frequency": 8},
                              valem_em=("Vibration",))),
            na_frente=("fps", "acao")),  # (noqa-acento): chave
    Imersao("recuo-pesado", "Recuo pesado", "metralhadora",
            "Solavancos espaçados e fortes, como arma de calibre grande.",
            {"Machine": {"start": 0, "end": 9, "strength": 8, "frequency": 6},
             "AutoGun": {"start": 2, "strength": 8, "frequency": 6},
             "Vibration": {"position": 0, "amplitude": 8, "frequency": 6}},
            {"fps": {"AutoGun": {"start": 2, "strength": 8, "frequency": 10}}},
            na_frente=("fps", "acao")),  # (noqa-acento): chave
    # --- Arco ---------------------------------------------------------------------------
    Imersao("corda-que-treme-no-fim", "Corda que treme no fim", "arco",
            "A força sobe do começo ao fim do curso, e pesa mais"
            " a cada meio segundo segurando.",
            {"Bow": {"start": 0, "end": 8, "force": 7, "snap": 6}},
            {"arco": {"Bow": {"start": 0, "end": 8, "force": 6, "snap": 7}}},
            # Começa leve no aperto (a rampa só dá os degraus depois do primeiro).
            (Momento("segurando", 0, "Bow", {"force": 1}), *_rampa("Bow", "force", 1, 7, 500)),
            na_frente=("arco", "aventura")),
    Imersao("flecha-que-escapa", "Flecha que escapa", "arco",
            "O estalo da soltura chega seco, no fim do curso.",
            {"Bow": {"start": 2, "end": 8, "force": 6, "snap": 7}},
            {"arco": {"Bow": {"start": 2, "end": 8, "force": 6, "snap": 8}}},
            na_frente=("arco", "aventura")),
    Imersao("braco-cansado", "Braço cansado", "arco",
            "A corda pesa menos e solta branda, e o braço treme depois de 3 s segurando.",
            {"Bow": {"start": 1, "end": 9, "force": 5, "snap": 5}},
            momentos=(Momento("segurando", 3000, "Vibration",
                              {"position": 6, "amplitude": 2, "frequency": 8}),),
            na_frente=("arco", "aventura")),
    # --- Resistência, Rígido, Rígido simples e Ponto duro --------------------------------
    Imersao("freio-abs-que-pulsa", "Freio que pulsa", "resistência",
            "Resistência firme no começo do curso, e o pedal pulsa"
            " depois de um instante segurando.",
            {"Resistance": {"start": 2, "force": 6},
             "Rigid": {"position": 2, "force": 220},
             "SimpleRigid": {"strength": 7},
             "Feedback": {"position": 2, "strength": 6}},
            {"corrida": {"Resistance": {"start": 2, "force": 7}}},
            (Momento("segurando", 800, "Vibration",
                     {"position": 2, "amplitude": 3, "frequency": 15}),),
            na_frente=("corrida",)),
    Imersao("pedal-no-fundo", "Pedal no fundo", "resistência",
            "A resistência começa cedo e fica forte, como pedal duro.",
            {"Resistance": {"start": 1, "force": 8},
             "Rigid": {"position": 1, "force": 240},
             "SimpleRigid": {"strength": 8},
             "Feedback": {"position": 1, "strength": 8}},
            {"simulacao": {"Resistance": {"start": 1, "force": 7}}},
            na_frente=("corrida", "simulacao")),
    Imersao("porta-emperrada", "Porta emperrada", "resistência",
            "Resistência leve que só começa no meio do curso.",
            {"Resistance": {"start": 4, "force": 4},
             "Rigid": {"position": 4, "force": 160},
             "SimpleRigid": {"strength": 4},
             "Feedback": {"position": 4, "strength": 4}},
            momentos=_rampa("Resistance", "force", 4, 6, 300000, quando="sempre",
                            valem_em=("Resistance",)),
            na_frente=("esportes",)),
    # --- Galope --------------------------------------------------------------------------
    Imersao("galope-no-chao", "Galope no chão", "galope",
            "Patas lentas e baixas, só se sentem devagar.",
            {"Galloping": {"start": 0, "end": 9, "first_foot": 6, "second_foot": 3,
                           "frequency": 6}},
            na_frente=("aventura",), a_validar=True),
    Imersao("motor-que-sobe", "Motor que sobe", "galope",
            "Passadas iguais que aceleram enquanto você segura, como um motor girando.",
            {"Galloping": {"start": 0, "end": 9, "first_foot": 5, "second_foot": 5,
                           "frequency": 12}},
            momentos=_rampa("Galloping", "frequency", 12, 36, 500),
            na_frente=("aventura", "corrida"), a_validar=True),
    Imersao("terreno-que-muda", "Terreno que muda", "galope",
            "Passadas desiguais, uma fraca e uma forte, como piso irregular.",
            {"Galloping": {"start": 1, "end": 8, "first_foot": 4, "second_foot": 6,
                           "frequency": 16}},
            na_frente=("aventura", "corrida"), a_validar=True),
    # --- Pulso (curvas A e B) --------------------------------------------------------------
    Imersao("batida-do-coracao", "Batida do coração", "pulso",
            "Um pulso médio no meio do curso, e uma batida forte quase a cada segundo.",
            {"PulseA": {"start": 2, "end": 6, "force": 150},
             "PulseB": {"start": 2, "end": 6, "force": 150}},
            momentos=(Momento("sempre", 0, "PulseB", {"force": 255}, dura_ms=120,
                              a_cada_ms=830),),
            na_frente=("terror",), a_validar=True),
    Imersao("arma-pesada", "Arma pesada", "pulso",
            "Um pulso forte a cada aperto.",
            {"PulseA": {"start": 1, "end": 8, "force": 255},
             "PulseB": {"start": 1, "end": 8, "force": 255}},
            na_frente=("terror",), a_validar=True),
    Imersao("aperto-que-trava", "Aperto que trava", "pulso",
            "Um pulso forte da metade ao fim do curso, e o gatilho trava"
            " um instante a cada aperto.",
            {"PulseA": {"start": 3, "end": 8, "force": 230},
             "PulseB": {"start": 3, "end": 8, "force": 230}},
            momentos=(Momento("ao_apertar", 0, "Feedback",
                              {"position": 8, "strength": 8}, dura_ms=300),),
            na_frente=("terror",), a_validar=True),
)

POR_CHAVE: dict[str, Imersao] = {i.chave: i for i in IMERSOES}


def _familia_do_modo(modo: str) -> str:
    """A família do acionamento, ou `""` quando ele não tem imersões."""
    for familia, modos in FAMILIAS.items():
        if modo in modos:
            return familia
    return ""


def imersoes_do_acionamento(modo: str, estilo: str = "") -> tuple[Imersao, ...]:
    """As três do acionamento, na ordem da tabela; com `estilo`, as dele vão na frente."""
    familia = _familia_do_modo(modo)
    delas = tuple(i for i in IMERSOES if i.familia == familia and modo in i.ajustes)
    if not estilo:
        return delas
    return tuple(sorted(delas, key=lambda i: estilo not in i.na_frente))


def ajustes_da_imersao(imersao: Imersao, modo: str, estilo: str = "") -> dict[str, int] | None:
    """Os ajustes dela naquele modo (a variante do estilo sobreposta), ou `None`."""
    base = imersao.ajustes.get(modo)
    if base is None:
        return None
    return {**base, **imersao.variantes.get(estilo, {}).get(modo, {})}


def todos_os_ajustes() -> Iterator[tuple[Imersao, str, str, dict[str, int]]]:
    """`(imersão, modo, estilo, ajustes)` de cada linha: a base (estilo `""`) e as variantes."""
    for imersao in IMERSOES:
        for modo in imersao.ajustes:
            yield imersao, modo, "", dict(imersao.ajustes[modo])
        for estilo, por_modo in imersao.variantes.items():
            for modo in por_modo:
                ajustes = ajustes_da_imersao(imersao, modo, estilo)
                if ajustes is not None:
                    yield imersao, modo, estilo, ajustes


def momentos_no_modo(imersao: Imersao, modo: str) -> tuple[Momento, ...]:
    """Os momentos dela que valem com o acionamento em `modo` (o `valem_em` de cada um)."""
    return tuple(m for m in imersao.momentos if not m.valem_em or modo in m.valem_em)


def imersao_dos_numeros(modo: str, params: Sequence[object]) -> tuple[Imersao, str] | None:
    """A imersão (e o estilo da variante, `""` na base) cujos números SÃO estes, ou `None`.

    Os `params` são os do perfil, posicionais na ordem do modo. A régua da aba prende a
    unicidade dos números, então o par (modo, params) diz a imersão sem campo no perfil.
    """
    from hefesto_dualsense4unix.app.actions.trigger_specs import (
        get_spec,
        preset_to_positional_params,
    )

    spec = get_spec(modo)
    if spec is None:
        return None
    alvo: list[int] = []
    for valor in params:
        if isinstance(valor, bool) or not isinstance(valor, int):
            return None  # o aninhado dos modos por posição não é de imersão nenhuma
        alvo.append(valor)
    for imersao, do_modo, estilo, ajustes in todos_os_ajustes():
        if do_modo == modo and list(preset_to_positional_params(spec, ajustes)) == alvo:
            return imersao, estilo
    return None


def a_da_frente_com_tempo(modo: str, estilo: str) -> Imersao | None:
    """No automático: a primeira imersão que o estilo põe na frente e que tem momento no modo."""
    for imersao in imersoes_do_acionamento(modo, estilo):
        if estilo in imersao.na_frente and momentos_no_modo(imersao, modo):
            return imersao
    return None
