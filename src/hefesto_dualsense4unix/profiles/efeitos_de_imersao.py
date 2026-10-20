"""Efeitos de imersão: os de cada acionamento da lista de onze, com variante por estilo de jogo.

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

import functools
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field

#: acionamento (família de modos) → os modos que a compõem
FAMILIAS: dict[str, tuple[str, ...]] = {
    "arma": ("Weapon",),
    "metralhadora": ("Machine", "Vibration"),
    "arco": ("Bow",),
    "resistência": ("Resistance",),
    "curva": ("MultiPositionFeedback",),
    "galope": ("Galloping",),
    "rampa": ("SlopeFeedback",),
    "vibração por posição": ("MultiPositionVibration",),
}

Ajustes = Mapping[str, int]


#: O-MOTOR-DOS-MOMENTOS-NAO-REESCREVE-O-BLOCO-E-LE-O-CLIQUE-01 (15/10/2026): dois `quando` além de
#: `ao_apertar`, `segurando` e `sempre`.
#: `passou_do_clique`: o Disparo passou do clique (o status 2 do report de entrada). Sem o status,
#: o `apos_ms` conta do aperto: o momento nunca fica mudo.
QUANDO_PASSOU_DO_CLIQUE = "passou_do_clique"
#: `pronto`: toma o gatilho por pouco tempo (de `PRONTO_MIN_MS` a `PRONTO_MAX_MS`), por cima de
#: qualquer outro momento, e devolve o bloco de antes. Conta no teto de escritas.
QUANDO_PRONTO = "pronto"
PRONTO_MIN_MS = 60
PRONTO_MAX_MS = 150


@dataclass(frozen=True)
class Momento:
    """Uma mudança no tempo: `quando` (ao apertar, segurando, sempre, passou do clique, pronto)
    + `apos_ms`.

    O `apos_ms` conta do aperto (do começo da imersão, no `sempre`; do clique, se o status chega,
    no `passou_do_clique`). A repetição do `a_cada_ms` só escreve quando o bloco muda.
    """

    quando: str
    apos_ms: int
    modo: str
    ajustes: Ajustes
    dura_ms: int | None = None
    a_cada_ms: int | None = None
    #: os modos do acionamento em que ele vale; vazio vale em todos
    valem_em: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.quando == QUANDO_PRONTO and not (
                self.dura_ms is not None and PRONTO_MIN_MS <= self.dura_ms <= PRONTO_MAX_MS):
            raise ValueError(
                f"o momento «pronto» dura de {PRONTO_MIN_MS} a {PRONTO_MAX_MS} ms, "
                f"não {self.dura_ms}")


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


def _curva(*forcas: int) -> dict[str, int]:
    """Os dez degraus da Curva de força, `pos_0` a `pos_9`."""
    return {f"pos_{i}": f for i, f in enumerate(forcas)}


#: O `na_frente` de cada uma é a `frente` de cada estilo na tabela `S` da página de 19/10/2026
#: (de 1 a 5 por estilo). O que a página põe na frente e ainda não existe (Golpe · falha, Golpe ·
#: aparo, Travar · esgotado) fica para o bloco C; o `sem-efeito` da frente é o «Nenhum» da tela.
IMERSOES: tuple[Imersao, ...] = (
    # --- Arma: Disparo ----------------------------------------------------------------------
    Imersao("ferrolho-que-volta", "Ferrolho que volta", "arma",
            "O gatilho rearma sozinho a cada tiro, firme e curto.",
            {"Weapon": {"start": 2, "end": 6, "force": 210}},
            na_frente=("fps", "luta", "esportes", "ritmo")),
    Imersao("trava-seca", "Trava seca", "arma",
            "Pouco curso e muita resistência, como arma sem munição.",
            {"Weapon": {"start": 2, "end": 3, "force": 255}},
            na_frente=("fps", "terror")),
    Imersao("pino-que-falha", "Pino que falha", "arma",
            "O disparo fica fundo e duro, e emperra meio segundo a cada aperto.",
            {"Weapon": {"start": 3, "end": 7, "force": 230}},
            momentos=(Momento("ao_apertar", 0, "Resistance",
                              {"start": 5, "force": 8}, dura_ms=500),),
            na_frente=()),
    Imersao("batida-do-coracao", "Batida do coração", "arma",
            "Um pulso médio no meio do curso.",
            {"Weapon": {"start": 2, "end": 6, "force": 150}},
            na_frente=("terror",), a_validar=True),
    Imersao("arma-pesada", "Arma pesada", "arma",
            "Um disparo duro e fundo a cada aperto.",
            {"Weapon": {"start": 2, "end": 8, "force": 255}},
            na_frente=(), a_validar=True),
    Imersao("aperto-que-trava", "Aperto que trava", "arma",
            "O gatilho trava um instante no fundo a cada aperto.",
            {"Weapon": {"start": 3, "end": 8, "force": 230}},
            momentos=(Momento("ao_apertar", 0, "Resistance",
                              {"start": 8, "force": 8}, dura_ms=300),),
            na_frente=(), a_validar=True),
    Imersao("golpe-leve", "Golpe leve", "arma",
            "Um clique curto e macio no meio do curso.",
            {"Weapon": {"start": 3, "end": 5, "force": 32}},
            na_frente=("acao", "esportes", "plataforma", "retro",  # (noqa-acento): chave
                       "maratona", "point_and_click", "visual_novel")),
    Imersao("golpe-pesado", "Golpe pesado", "arma",
            "Parede longa e dura que estala no fundo.",
            # Na luta o catálogo pedia 2/8/255, que é a Arma pesada: sem variante, a tela não
            # distinguiria as duas pelos números.
            {"Weapon": {"start": 2, "end": 8, "force": 191}},
            na_frente=("terror",)),
    Imersao("clique-no-meio", "Clique no meio", "arma",
            "Um clique na metade, e a resistência cresce depois dele.",
            {"Weapon": {"start": 4, "end": 6, "force": 160}},
            # Com o status do Disparo o momento nasce no clique; sem ele, 300 ms do aperto.
            momentos=(Momento(QUANDO_PASSOU_DO_CLIQUE, 300, "Resistance",
                              {"start": 7, "force": 6}),),
            na_frente=("fps", "furtivo", "retro")),
    # --- Metralhadora: Metralhadora e Vibração -------------------------------------------------
    Imersao("rajada-que-sobe-sozinha", "Rajada que sobe sozinha", "metralhadora",
            "As batidas começam médias e ficam mais fortes a cada meio segundo segurando.",
            {"Machine": {"start": 0, "end": 9, "strength": 4, "frequency": 40},
             "Vibration": {"position": 0, "amplitude": 5, "frequency": 8}},
            # Uma escrita por degrau; o firmware faz o ritmo, nenhum `a_cada_ms` repete o bloco.
            momentos=(Momento("segurando", 500, "Machine", {"strength": 5}, valem_em=("Machine",)),
                      Momento("segurando", 1000, "Machine", {"strength": 6},
                              valem_em=("Machine",)),
                      Momento("segurando", 1500, "Machine", {"strength": 7},
                              valem_em=("Machine",)),
                      Momento("segurando", 500, "Vibration", {"amplitude": 6},
                              valem_em=("Vibration",)),
                      Momento("segurando", 1000, "Vibration", {"amplitude": 7},
                              valem_em=("Vibration",)),
                      Momento("segurando", 1500, "Vibration", {"amplitude": 8},
                              valem_em=("Vibration",))),
            na_frente=("fps",)),
    Imersao("cano-que-esquenta", "Cano que esquenta", "metralhadora",
            "Batidas rápidas e fortes que ficam lentas e pesadas depois de 3 s segurando.",
            {"Machine": {"start": 0, "end": 9, "strength": 6, "frequency": 20},
             "Vibration": {"position": 0, "amplitude": 6, "frequency": 20}},
            momentos=(Momento("segurando", 3000, "Machine", {"frequency": 8},
                              valem_em=("Machine",)),
                      Momento("segurando", 3000, "Vibration", {"frequency": 8},
                              valem_em=("Vibration",))),
            na_frente=()),
    Imersao("recuo-pesado", "Recuo pesado", "metralhadora",
            "Solavancos espaçados e fortes, como arma de calibre grande.",
            {"Machine": {"start": 0, "end": 9, "strength": 8, "frequency": 6},
             "Vibration": {"position": 0, "amplitude": 8, "frequency": 6}},
            na_frente=("fps",)),
    # --- Arco ---------------------------------------------------------------------------
    Imersao("corda-que-estica", "Corda que estica", "arco",
            "A corda começa leve e pesa mais a cada meio segundo segurando.",
            {"Bow": {"start": 0, "end": 8, "force": 7, "snap": 6}},
            {"arco": {"Bow": {"start": 0, "end": 8, "force": 6, "snap": 7}}},
            # Começa leve no aperto (a rampa só dá os degraus depois do primeiro).
            (Momento("segurando", 0, "Bow", {"force": 1}), *_rampa("Bow", "force", 1, 7, 500)),
            na_frente=("acao", "plataforma")),  # (noqa-acento): chave
    Imersao("flecha-que-escapa", "Flecha que escapa", "arco",
            "O estalo da soltura chega seco, no fim do curso.",
            {"Bow": {"start": 2, "end": 8, "force": 6, "snap": 7}},
            {"arco": {"Bow": {"start": 2, "end": 8, "force": 6, "snap": 8}}},
            na_frente=("furtivo", "aventura")),
    Imersao("braco-cansado", "Braço cansado", "arco",
            "A corda pesa menos e solta branda, e o braço treme depois de 3 s segurando.",
            {"Bow": {"start": 1, "end": 9, "force": 5, "snap": 5}},
            momentos=(Momento("segurando", 3000, "Vibration",
                              {"position": 6, "amplitude": 2, "frequency": 8}),),
            na_frente=()),
    # --- Resistência e Curva de força --------------------------------------------------------
    Imersao("freio-abs-que-pulsa", "Freio que pulsa", "resistência",
            "Resistência firme no começo, e o pedal pulsa depois de um instante segurando.",
            {"Resistance": {"start": 2, "force": 6}},
            {"corrida": {"Resistance": {"start": 2, "force": 7}}},
            (Momento("segurando", 800, "Vibration",
                     {"position": 2, "amplitude": 3, "frequency": 15}),),
            na_frente=()),
    Imersao("pedal-duro", "Pedal duro", "resistência",
            "A resistência começa cedo e fica forte, como pedal duro.",
            {"Resistance": {"start": 1, "force": 8}},
            {"simulacao": {"Resistance": {"start": 1, "force": 7}}},
            na_frente=("corrida", "simulacao")),
    # O Pique vem antes do Golpe carregado: nos Esportes ele é o da frente (CATALOGO §2.4).
    Imersao("pique-que-cansa", "Pique que cansa", "resistência",
            "Um peso leve que vai pesando segurando a corrida: mais forte aos 2, 4 e 6 s.",
            {"Resistance": {"start": 0, "force": 2}},
            momentos=(Momento("segurando", 2000, "Resistance", {"force": 3}),
                      Momento("segurando", 4000, "Resistance", {"force": 4}),
                      Momento("segurando", 6000, "Resistance", {"force": 5})),
            na_frente=("souls",)),
    Imersao("golpe-carregado", "Golpe carregado", "resistência",
            "Uma parede que endurece segurando, treme de pronto aos 1,5 s e some.",
            {"Resistance": {"start": 4, "force": 3}},
            # O pronto (150 ms de Metralhadora, por cima de tudo) e depois a parede some.
            momentos=(Momento("segurando", 500, "Resistance", {"force": 5}),
                      Momento("segurando", 1000, "Resistance", {"force": 7}),
                      Momento(QUANDO_PRONTO, 1500, "Machine",
                              {"start": 4, "end": 9, "strength": 3, "frequency": 40},
                              dura_ms=150),
                      Momento("segurando", 1650, "Off", {})),
            na_frente=("acao", "luta", "souls")),  # (noqa-acento): chave
    Imersao("mira-firme", "Mira firme", "resistência",
            "Peso leve e constante no gatilho da mira.",
            {"Resistance": {"start": 2, "force": 3}},
            na_frente=("furtivo", "simulacao", "esportes", "plataforma", "retro", "maratona")),
    Imersao("porta-emperrada", "Porta emperrada", "curva",
            "O gatilho range em degraus, como porta enferrujada.",
            {"MultiPositionFeedback": _curva(0, 0, 0, 6, 0, 6, 0, 6, 0, 6)},
            na_frente=("aventura", "terror")),
    Imersao("escudo-que-aguenta", "Escudo que aguenta", "curva",
            "O gatilho endurece do meio ao fim e fica mais duro depois de 2 s segurando.",
            {"MultiPositionFeedback": _curva(0, 0, 2, 2, 3, 4, 5, 6, 7, 8)},
            momentos=(Momento("segurando", 2000, "MultiPositionFeedback",
                              _curva(0, 0, 3, 3, 4, 5, 6, 7, 8, 8)),),
            na_frente=("acao",)),  # (noqa-acento): chave
    Imersao("duas-travas", "Duas travas", "curva",
            "Duas travas no curso, uma na entrada e outra no meio.",
            {"MultiPositionFeedback": _curva(1, 2, 8, 0, 0, 1, 2, 8, 0, 0)},
            na_frente=()),
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
            # Até 33 Hz qualquer valor é limpo; acima disso só os que dividem 1000.
            momentos=_rampa("Galloping", "frequency", 12, 33, 500),
            na_frente=("corrida",), a_validar=True),
    Imersao("terreno-que-muda", "Terreno que muda", "galope",
            "Passadas desiguais, uma fraca e uma forte, como piso irregular.",
            {"Galloping": {"start": 1, "end": 8, "first_foot": 4, "second_foot": 6,
                           "frequency": 16}},
            na_frente=("corrida",), a_validar=True),
    # --- Rampa de força e Vibração por posição -----------------------------------------------
    Imersao("besta", "Besta", "rampa",
            "Rampa curta e dura, que solta seca.",
            {"SlopeFeedback": {"start": 2, "end": 9, "start_strength": 5, "end_strength": 8}},
            na_frente=("aventura",)),
    Imersao("agarrar", "Agarrar", "rampa",
            "O gatilho resiste mais à medida que aperta, como apertar algo.",
            {"SlopeFeedback": {"start": 2, "end": 8, "start_strength": 2, "end_strength": 6}},
            na_frente=("aventura",)),
    Imersao("energia-que-cresce", "Energia que cresce", "vibração por posição",
            "Vibração que fica mais forte quanto mais fundo vai o dedo, e cheia aos 1,5 s.",
            {"MultiPositionVibration": {"frequency": 50, **_curva(0, 1, 2, 3, 4, 5, 6, 7, 8, 8)}},
            {"corrida": {"MultiPositionVibration": {"frequency": 25}}},
            (Momento("segurando", 1500, "Machine",
                     {"start": 2, "end": 9, "strength": 8, "frequency": 50}),),
            na_frente=("acao",)),  # (noqa-acento): chave
    Imersao("motor-no-acelerador", "Motor no acelerador", "vibração por posição",
            "Ronco fraco que cresce com o pedal.",
            {"MultiPositionVibration": {"frequency": 25, **_curva(1, 1, 2, 2, 3, 3, 4, 4, 5, 5)}},
            na_frente=("simulacao",)),
)

#: Os números de ontem de cada imersão que mudou: `(imersão, chave de ontem, ajustes de ontem)`.
#: Um perfil salvo com eles abre com a imersão de hoje selecionada (`imersao_dos_numeros`). A
#: chave de ontem pode ser uma que saiu da lista de onze: ela passa pela tradução do perfil.
NUMEROS_DE_ONTEM: tuple[tuple[str, str, Mapping[str, int]], ...] = (
    ("ferrolho-que-volta", "SemiAutoGun", {"start": 3, "end": 7, "force": 6}),
    ("trava-seca", "SemiAutoGun", {"start": 2, "end": 3, "force": 8}),
    ("trava-seca", "Weapon", {"start": 0, "end": 1, "force": 255}),
    ("pino-que-falha", "SemiAutoGun", {"start": 4, "end": 6, "force": 7}),
    ("batida-do-coracao", "PulseB", {"start": 2, "end": 6, "force": 150}),
    ("arma-pesada", "PulseB", {"start": 1, "end": 8, "force": 255}),
    ("aperto-que-trava", "PulseB", {"start": 3, "end": 8, "force": 230}),
    ("rajada-que-sobe-sozinha", "Machine", {"start": 0, "end": 9, "strength": 5, "frequency": 8}),
    ("rajada-que-sobe-sozinha", "Machine", {"start": 0, "end": 9, "strength": 5, "frequency": 24}),
    ("rajada-que-sobe-sozinha", "AutoGun", {"start": 1, "strength": 7, "frequency": 16}),
    ("rajada-que-sobe-sozinha", "AutoGun", {"start": 1, "strength": 7, "frequency": 60}),
    ("cano-que-esquenta", "AutoGun", {"start": 1, "strength": 6, "frequency": 20}),
    ("recuo-pesado", "AutoGun", {"start": 2, "strength": 8, "frequency": 6}),
    ("recuo-pesado", "AutoGun", {"start": 2, "strength": 8, "frequency": 10}),
    ("freio-abs-que-pulsa", "Rigid", {"position": 2, "force": 220}),
    ("freio-abs-que-pulsa", "SimpleRigid", {"strength": 7}),
    ("freio-abs-que-pulsa", "Feedback", {"position": 2, "strength": 6}),
    ("pedal-duro", "Rigid", {"position": 1, "force": 240}),
    ("pedal-duro", "SimpleRigid", {"strength": 8}),
    ("pedal-duro", "Feedback", {"position": 1, "strength": 8}),
)

POR_CHAVE: dict[str, Imersao] = {i.chave: i for i in IMERSOES}


def _estilo_de_hoje(estilo: str) -> str:
    """A chave de hoje do estilo: o perfil salvo com o Arco vale pela Ação."""
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import chave_do_catalogo

    return str(chave_do_catalogo(estilo))


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
    estilo = _estilo_de_hoje(estilo)
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
    achada = _numeros_de_ontem().get((modo, tuple(alvo)))
    return None if achada is None else (achada, "")


@functools.lru_cache(maxsize=1)
def _numeros_de_ontem() -> dict[tuple[str, tuple[int, ...]], Imersao]:
    """`(modo, posicionais de hoje)` → a imersão cujos números de ontem eram esses.

    Cada linha de :data:`NUMEROS_DE_ONTEM` passa pela tradução do perfil (a chave que saiu da
    lista de onze vira a de hoje). Só vale se a imersão de hoje tem aquele modo: o campo da tela
    nunca mostra uma opção que a lista do acionamento não oferece.
    """
    from hefesto_dualsense4unix.app.actions.trigger_specs import (
        get_spec,
        preset_to_positional_params,
    )
    from hefesto_dualsense4unix.core.trigger_effects import traduzir_chave_velha

    mapa: dict[tuple[str, tuple[int, ...]], Imersao] = {}
    for chave, velha, ajustes in NUMEROS_DE_ONTEM:
        spec = get_spec(velha)
        if spec is None:
            continue
        posicionais = [int(v) for v in preset_to_positional_params(spec, dict(ajustes))]
        traduzida = traduzir_chave_velha(velha, posicionais)
        modo, params = traduzida if traduzida is not None else (velha, posicionais)
        imersao = POR_CHAVE[chave]
        if modo in imersao.ajustes:
            mapa.setdefault((modo, tuple(params)), imersao)
    return mapa


def a_da_frente_com_tempo(modo: str, estilo: str) -> Imersao | None:
    """No automático: a primeira imersão que o estilo põe na frente e que tem momento no modo."""
    estilo = _estilo_de_hoje(estilo)
    for imersao in imersoes_do_acionamento(modo, estilo):
        if estilo in imersao.na_frente and momentos_no_modo(imersao, modo):
            return imersao
    return None
