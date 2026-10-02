"""O padrão do computador: o que não muda com o jogo, e o perfil que só sobrepõe.

O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01 (01/10/2026). Ela, depois de uma
noite com visitas: *«algumas features precisam ser por computador e permanecerem
salvas»*. O som, os sensores, a luz, a vibração, o mouse e o teclado passam a ter
um valor do computador, guardado no ``maquina.json`` (``computador``), um por
controle e um para todo controle. O perfil do jogo só guarda o que for diferente
(`D-0110-O-COMPUTADOR-DA-O-PADRAO-O-JOGO-SOBREPOE`, por delegação).

UM DONO PARA QUATRO PERGUNTAS:

- :data:`SECOES`: o que é do computador, cartão a cartão, e :data:`DO_JOGO`, o
  que fica no jogo e por quê;
- :func:`perfil_que_vale`: a vista que todo leitor aplica, no molde da
  economia (``manager._perfil_na_economia``): memória, nunca disco;
- :func:`gravar` e :func:`gravar_pelo_gesto`: o único escritor de um cartão do
  computador. Grava no perfil quando ele já sobrepõe o cartão, ou quando o
  gesto é «Só neste jogo»; nos outros casos, no computador;
- :func:`migrar_uma_vez`: o computador nasce do Freestyle, e o perfil perde só
  o que já vale igual.

A PRECEDÊNCIA, campo a campo::

    o jogo, neste controle  >  o jogo, global  >  o computador, neste controle
      >  o computador, todo controle  >  o de fábrica

O QUE CONTA COMO ESCOLHA DO JOGO. Um campo que o perfil escreveu
(``model_fields_set``) e que não é ``None`` (``None`` é «sem opinião» no esquema
inteiro). As três seções globais que o ``save_profile`` grava sempre inteiras
(``leds``, ``rumble`` e as velocidades do ``mouse``) têm uma regra a mais: o
valor de fábrica não conta como escolha. Qualquer gravação de perfil escreve
essas seções por extenso, e o valor de fábrica ali não diz se alguém o
escolheu. É a resposta 4 dela de 01/10 («os campos de luz e vibração que
guardam o valor de fábrica passam a seguir o computador»), estendida às duas
velocidades pela mesma razão. As entradas de cada controle são gravadas só com
o que foi escrito (``exclude_unset``), e ali a presença basta.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterable, Mapping
from typing import Any, NamedTuple

from hefesto_dualsense4unix.profiles.schema import (
    ControllerMicOverride,
    ControllerRumbleOverride,
    ControllerSensoresOverride,
    LedsConfig,
    Profile,
    ProfileMouseConfig,
    ProfileSpeakerConfig,
    RumbleConfig,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


class Secao(NamedTuple):
    """Um cartão da tela cujo valor é do computador.

    ``globais`` são as seções de topo do perfil que o cartão mostra;
    ``no_computador`` é o subconjunto que o computador guarda no ``global``;
    ``por_controle`` são as seções de ``controllers[<identidade>]``.
    """

    cartao: str
    pagina: str
    rotulo: str
    globais: tuple[str, ...]
    no_computador: tuple[str, ...]
    por_controle: tuple[str, ...]


#: O QUE É DO COMPUTADOR, cartão a cartão. A única declaração: a vista, o
#: escritor, a migração e a marca da tela leem daqui.
SECOES: dict[str, Secao] = {
    "som": Secao("som", "02-controles.html", "Som",
                 ("speaker", "mic"), ("speaker",), ("speaker", "mic")),
    "sensores": Secao("sensores", "02-controles.html", "Sensores",
                      (), (), ("sensores",)),
    "luz": Secao("luz", "04-iluminacao.html", "Luz",
                 ("leds",), ("leds",), ("leds",)),
    "vibracao": Secao("vibracao", "05-vibracao.html", "Vibração",
                      ("rumble",), ("rumble",), ("rumble",)),
    "mouse": Secao("mouse", "06-navegacao.html", "Mouse",
                   ("mouse", "button_actions"), ("mouse", "button_actions"), ()),
    "teclado": Secao("teclado", "06-navegacao.html", "Teclado",
                     ("teclado_emulado", "key_bindings"),
                     ("teclado_emulado", "key_bindings"), ()),
}

#: O QUE FICA NO JOGO, e por quê. É o «desenho do jogo»: nenhum jogo precisa
#: dele no computador. Se um dia ela quiser um destes no computador, é uma linha
#: a menos aqui e uma a mais em :data:`SECOES`.
DO_JOGO: dict[str, str] = {
    "mode": "o modo (Sony, Xbox, Navegação, Nativo) é de cada jogo",
    "mascara": "como o controle aparece no jogo",
    "movimento": "a Mira é do jogo que mira",
    "triggers": "os gatilhos são o efeito de cada jogo",
    "remapeamento": "a troca de botões é do jogo",
    "mouse.enabled": "o Point-and-click liga com o jogo de mouse",
    "suppress_desktop_emulation": "o modo-jogo é de cada jogo",
}

#: O que já era do computador antes desta sprint, com o dono de antes.
JA_DO_COMPUTADOR: dict[str, str] = {
    "mic.button_toggles_system": "D-O-MICROFONE-A-MAQUINA-DA-O-PADRAO-O-PERFIL-SOBREPOE",
}

#: As seções que só fazem sentido juntas: quem escolhe uma escolhe o par.
PARES: dict[str, tuple[tuple[str, ...], ...]] = {
    "rumble": (("policy", "custom_mult"),),
    "leds": (("lightbar", "lightbar_para_o_numero"),),
}

#: As seções globais que o ``save_profile`` grava inteiras, com o valor de
#: fábrica de cada campo (ver o cabeçalho).
_DENSAS: dict[str, dict[str, Any]] = {
    "leds": LedsConfig().model_dump(mode="json"),
    "rumble": RumbleConfig().model_dump(mode="json"),
    "mouse": {
        campo: ProfileMouseConfig.model_fields[campo].default
        for campo in ("speed", "scroll_speed")
    },
}

#: As seções que são modelo (dicionário de campos). As outras são valor inteiro.
_MODELOS: frozenset[str] = frozenset(
    {"leds", "rumble", "speaker", "mic", "sensores", "mouse"}
)

#: Os campos de cada seção de controle (os modelos do perfil, nunca digitados).
_CAMPOS_DO_CONTROLE: dict[str, tuple[str, ...]] = {
    "leds": tuple(LedsConfig.model_fields),
    "speaker": tuple(ProfileSpeakerConfig.model_fields),
    "mic": tuple(ControllerMicOverride.model_fields),
    "rumble": tuple(ControllerRumbleOverride.model_fields),
    "sensores": tuple(ControllerSensoresOverride.model_fields),
}

COMPUTADOR = "computador"
JOGO = "jogo"


class OFreestyleNaoSobrepoeError(RuntimeError):
    """«Só neste jogo» pedido com o Freestyle: ele não sobrepõe nada."""


class OJogoNaoTeriaOQueGuardarError(RuntimeError):
    """«Só neste jogo» que não daria ao jogo escolha nenhuma naquele cartão.

    A marca não oferece o botão nesse caso (:func:`pode_so_neste_jogo`); a
    recusa é para o clique que chega de um tique velho, e nunca grava.
    """


# ---------------------------------------------------------------------------
# A identidade do controle
# ---------------------------------------------------------------------------
def chave(endereco: object) -> str | None:
    """A identidade de um controle (doze hex minúsculos), ou ``None``."""
    from hefesto_dualsense4unix.utils.maquina import chave_do_controle

    return chave_do_controle(endereco)


def _entradas_por_chave(controles: Mapping[str, Any] | None) -> dict[str, str]:
    """``{identidade: chave como está no perfil}``."""
    saida: dict[str, str] = {}
    for original in controles or {}:
        normal = chave(original)
        if normal is not None:
            saida.setdefault(normal, original)
    return saida


def chave_no_perfil(perfil: Profile, uniq: object) -> str:
    """A chave da entrada deste controle como o perfil a escreveu.

    O perfil pode guardar o controle com dois-pontos ou colado, maiúsculo ou
    minúsculo; quem grava a entrada mexe na que existe, e não cria uma segunda
    para o mesmo controle. Sem entrada, a identidade (ou o próprio ``uniq``).
    """
    identidade = chave(uniq)
    original = _entradas_por_chave(perfil.controllers).get(identidade or "")
    return original or identidade or str(uniq)


# ---------------------------------------------------------------------------
# O que é escolha do jogo
# ---------------------------------------------------------------------------
def e_o_freestyle(nome: object) -> bool:
    """O Freestyle é o perfil de fora do jogo: ele não sobrepõe nada.

    A mesma pergunta de ``manager.e_o_freestyle`` (o slug do arquivo), sem
    importar o gerente.
    """
    from hefesto_dualsense4unix.profiles.loader import SLUG_DO_PADRAO
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    return isinstance(nome, str) and mesmo_slug(nome, SLUG_DO_PADRAO)


def _expandir_pares(secao: str, campos: Iterable[str]) -> set[str]:
    escolhidos = set(campos)
    for par in PARES.get(secao, ()):
        if escolhidos & set(par):
            escolhidos |= set(par)
    return escolhidos


def escolhas_globais_do_jogo(perfil: Profile, secao: str) -> dict[str, Any]:
    """Os campos da seção global ``secao`` que o jogo escolheu, com o valor (JSON).

    Para os valores inteiros (``button_actions``, ``key_bindings`` e
    ``teclado_emulado``) a resposta é ``{secao: valor}`` quando o perfil tem
    opinião, e ``{}`` quando não tem.
    """
    if secao not in perfil.model_fields_set or e_o_freestyle(perfil.name):
        return {}
    valor = getattr(perfil, secao, None)
    if valor is None:
        return {}
    if secao not in _MODELOS:
        return {secao: valor}
    dados = valor.model_dump(mode="json")
    fabrica = _DENSAS.get(secao)
    escolhidos = {
        campo for campo in valor.model_fields_set
        if campo in dados and dados[campo] is not None
        and (fabrica is None or campo not in fabrica or dados[campo] != fabrica[campo])
    }
    if secao == "mouse":
        escolhidos &= {"speed", "scroll_speed"}
    if secao == "mic":
        # O modo do microfone tem dono próprio (`JA_DO_COMPUTADOR`).
        escolhidos -= {"button_toggles_system"}
    return {campo: dados.get(campo) for campo in _expandir_pares(secao, escolhidos)}


def escolhas_do_controle_do_jogo(
    perfil: Profile, uniq: object, secao: str
) -> dict[str, Any]:
    """Os campos da seção ``secao`` do controle ``uniq`` que o jogo escreveu."""
    identidade = chave(uniq)
    if identidade is None or e_o_freestyle(perfil.name):
        return {}
    original = _entradas_por_chave(perfil.controllers).get(identidade)
    entrada = (perfil.controllers or {}).get(original) if original else None
    valor = getattr(entrada, secao, None) if entrada is not None else None
    if valor is None:
        return {}
    dados = valor.model_dump(mode="json", exclude_unset=True)
    escolhidos = {campo for campo, dado in dados.items() if dado is not None}
    return {campo: dados.get(campo) for campo in _expandir_pares(secao, escolhidos)}


def sobrepoe(perfil: Profile | None, cartao: str, uniq: object = None) -> bool:
    """O perfil tem escolha própria neste cartão (no global, ou neste controle)?"""
    if perfil is None:
        return False
    secao = SECOES[cartao]
    if any(escolhas_globais_do_jogo(perfil, s) for s in secao.globais):
        return True
    if uniq is None:
        return any(
            escolhas_do_controle_do_jogo(perfil, original, s)
            for original in (perfil.controllers or {})
            for s in secao.por_controle
        )
    return any(escolhas_do_controle_do_jogo(perfil, uniq, s) for s in secao.por_controle)


# ---------------------------------------------------------------------------
# A vista
# ---------------------------------------------------------------------------
def computador_vazio(computador: Any) -> bool:
    """O computador não declarou nada (a vista devolve o próprio perfil)."""
    if computador is None:
        return True
    return not computador.controles and not computador.global_.model_dump(
        exclude_unset=True, exclude_none=True)


def perfil_que_vale(perfil: Profile, computador: Any) -> Profile:
    """O perfil com o computador por baixo, na precedência do cabeçalho.

    Perfil e computador sem nada devolvem o MESMO objeto: quem nunca declarou
    nada aplica byte a byte o que aplicava. É memória: o disco não muda.
    """
    if computador_vazio(computador):
        return perfil
    cru: dict[str, Any] = perfil.model_dump(mode="json", exclude_unset=True)
    do_global = computador.global_
    for secao in ("leds", "rumble", "speaker", "mouse"):
        modelo = getattr(do_global, secao, None)
        if modelo is None:
            continue
        do_computador = modelo.model_dump(mode="json", exclude_unset=True)
        if not do_computador:
            continue
        if secao == "mouse" and perfil.mouse is None:
            # O liga e desliga é do jogo: sem a seção, as velocidades chegam
            # pelo recuo da Navegação (`daemon.lifecycle._velocidades_ou_as_da_sessao`).
            continue
        escolhas = escolhas_globais_do_jogo(perfil, secao)
        atual = dict(cru.get(secao) or {})
        for campo, valor in do_computador.items():
            if campo not in escolhas:
                atual[campo] = valor
        cru[secao] = atual
    # O FREESTYLE NÃO SOBREPÕE NADA, também na vista: o que o arquivo dele
    # ainda guarda de um cartão do computador (o «Status do Modo» e o «Salvar»
    # do rodapé o reescrevem) fica POR BAIXO do computador. Sem isto a marca
    # dizia «PC», o clique gravava no computador, e o aparelho recebia o
    # valor velho do Freestyle (medido na conferência de 02/10/2026).
    freestyle = e_o_freestyle(perfil.name)
    if do_global.button_actions is not None:
        acoes_do_jogo = perfil.button_actions or {}
        cru["button_actions"] = (
            {**acoes_do_jogo, **do_global.button_actions} if freestyle
            else {**do_global.button_actions, **acoes_do_jogo})
    if do_global.key_bindings is not None and (freestyle or perfil.key_bindings != {}):
        teclas_do_jogo = perfil.key_bindings or {}
        cru["key_bindings"] = (
            {**teclas_do_jogo, **do_global.key_bindings} if freestyle
            else {**do_global.key_bindings, **teclas_do_jogo})
    if do_global.teclado_emulado is not None and (freestyle or perfil.teclado_emulado is None):
        cru["teclado_emulado"] = do_global.teclado_emulado
    if computador.controles:
        cru["controllers"] = _controles_que_valem(perfil, cru.get("controllers"), computador)
    return Profile.model_validate(cru)


def _controles_que_valem(
    perfil: Profile, do_jogo: Mapping[str, Any] | None, computador: Any
) -> dict[str, Any]:
    entradas: dict[str, Any] = {k: dict(v) for k, v in (do_jogo or {}).items()}
    originais = _entradas_por_chave(entradas)
    freestyle = e_o_freestyle(perfil.name)
    globais = {
        secao: set(escolhas_globais_do_jogo(perfil, secao))
        for secao in ("leds", "rumble", "speaker", "mic")
    }
    for identidade, do_computador in computador.controles.items():
        dados = do_computador.model_dump(mode="json", exclude_unset=True)
        original = originais.get(identidade, identidade)
        entrada = dict(entradas.get(original) or {})
        for secao, campos in dados.items():
            if secao not in _CAMPOS_DO_CONTROLE or not isinstance(campos, Mapping):
                continue
            do_controle = dict(entrada.get(secao) or {})
            # O Freestyle não protege as próprias entradas: o computador vence.
            escritos = set() if freestyle else {
                c for c, v in do_controle.items() if v is not None}
            escolhidos = _expandir_pares(secao, escritos | globais.get(secao, set()))
            for campo, valor in campos.items():
                if campo not in escolhidos:
                    do_controle[campo] = valor
            if do_controle:
                entrada[secao] = do_controle
        if entrada:
            entradas[original] = entrada
    return entradas


def carregar_o_que_vale(nome: str) -> Profile:
    """``load_profile`` com o computador por baixo. É a leitura de quem APLICA.

    Quem grava continua lendo cru (``loader.load_profile``): o computador não
    pode ir parar no perfil.
    """
    from hefesto_dualsense4unix.profiles import loader

    return o_que_vale(loader.load_profile(nome))


def o_que_vale(perfil: Profile) -> Profile:
    """:func:`perfil_que_vale` com o computador do disco. Para quem já leu o perfil."""
    return perfil_que_vale(perfil, o_computador())


#: ``(selo do maquina.json, ComputadorDeclarado)``: a leitura de cada volta é um
#: ``stat``, e o JSON só se lê quando o arquivo muda. Os leitores do daemon
#: perguntam por aqui, e não ao ``Daemon._maquina``: a janela grava o arquivo
#: direto, e a memória do daemon só se refaz pelo ``machine.declare``.
_O_COMPUTADOR_LIDO: tuple[Any, Any] = (None, None)


def selo_da_maquina() -> tuple[int, int, int] | None:
    """``(inode, mtime_ns, tamanho)`` do ``maquina.json``, ou ``None`` sem arquivo."""
    from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina

    try:
        st = caminho_da_maquina().stat()
    except OSError:
        return None
    return (st.st_ino, st.st_mtime_ns, st.st_size)


def o_computador() -> Any:
    """O padrão do computador do disco (``ComputadorDeclarado``), relido quando muda."""
    global _O_COMPUTADOR_LIDO
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    selo = selo_da_maquina()
    lido_em, computador = _O_COMPUTADOR_LIDO
    if computador is None or selo is None or selo != lido_em:
        computador = carregar_maquina().computador
        _O_COMPUTADOR_LIDO = (selo, computador)
    return computador


def velocidades_do_computador() -> tuple[int | None, int | None]:
    """``(speed, scroll_speed)`` do mouse do computador, ou ``None`` no que falta."""
    with contextlib.suppress(Exception):
        mouse = o_computador().global_.mouse
        if mouse is not None:
            return mouse.speed, mouse.scroll_speed
    return None, None


# ---------------------------------------------------------------------------
# O escritor
# ---------------------------------------------------------------------------
def _remendar(destino: dict[str, Any], campos: Mapping[str, Any]) -> None:
    """``campos`` por cima de ``destino``; ``None`` tira o campo (ou a seção)."""
    for secao, valor in campos.items():
        if valor is None:
            destino.pop(secao, None)
            continue
        if secao in _MODELOS and isinstance(valor, Mapping):
            atual = dict(destino.get(secao) or {})
            for campo, dado in valor.items():
                if dado is None:
                    atual.pop(campo, None)
                else:
                    atual[campo] = dado
            if atual:
                destino[secao] = atual
            else:
                destino.pop(secao, None)
        else:
            destino[secao] = valor


def _com_os_pares(campos: Mapping[str, Any]) -> dict[str, Any]:
    """Quem muda um campo de um par muda o par: o colega que falta vira ``None``."""
    saida: dict[str, Any] = {}
    for secao, valor in campos.items():
        if secao in PARES and isinstance(valor, Mapping):
            valor = dict(valor)
            for par in PARES[secao]:
                if set(valor) & set(par):
                    for campo in par:
                        valor.setdefault(campo, None)
        saida[secao] = valor
    return saida


def _no_computador(campos: Mapping[str, Any], uniq: object) -> dict[str, Any]:
    """Os ``campos`` gravados no padrão do computador. Devolve o documento novo."""
    from hefesto_dualsense4unix.utils.maquina import gravar_o_computador

    documento: dict[str, Any] = dict(o_computador().model_dump(mode="json"))
    if uniq is None:
        do_global = dict(documento.get("global") or {})
        _remendar(do_global, {
            s: (_so_os_campos_do_computador(s, v) if isinstance(v, Mapping) else v)
            for s, v in campos.items() if s in _GLOBAIS_DO_COMPUTADOR
        })
        fora = sorted(s for s in campos if s not in _GLOBAIS_DO_COMPUTADOR)
        if fora:
            logger.info("computador_sem_lugar_para", secoes=fora)
        documento["global"] = do_global
    else:
        identidade = chave(uniq)
        if identidade is None:
            raise ValueError(f"o controle {uniq!r} não tem identidade para o computador")
        controles = dict(documento.get("controles") or {})
        entrada = dict(controles.get(identidade) or {})
        _remendar(entrada, {s: v for s, v in campos.items() if s in _CAMPOS_DO_CONTROLE})
        if entrada:
            controles[identidade] = entrada
        else:
            controles.pop(identidade, None)
        documento["controles"] = controles
    if not gravar_o_computador(documento):
        raise OSError("o maquina.json é de outra versão e não foi regravado")
    return documento


#: As seções globais em que o computador guarda MENOS que o perfil: do mouse,
#: só as velocidades (o liga e desliga é do jogo).
_CAMPOS_DO_GLOBAL: dict[str, tuple[str, ...]] = {"mouse": ("speed", "scroll_speed")}


def _so_os_campos_do_computador(secao: str, valor: Mapping[str, Any]) -> dict[str, Any]:
    campos = _CAMPOS_DO_GLOBAL.get(secao)
    return dict(valor) if campos is None else {c: v for c, v in valor.items() if c in campos}


_GLOBAIS_DO_COMPUTADOR: frozenset[str] = frozenset(
    s for secao in SECOES.values() for s in secao.no_computador
)


def _no_perfil(perfil: Profile, campos: Mapping[str, Any], uniq: object,
               origem: str | None) -> None:
    from hefesto_dualsense4unix.profiles.loader import save_profile

    cru = perfil.model_dump(mode="json", exclude_unset=True)
    if uniq is None:
        _remendar(cru, campos)
    else:
        identidade = chave(uniq)
        controles = dict(cru.get("controllers") or {})
        original = _entradas_por_chave(controles).get(identidade or "", identidade or str(uniq))
        entrada = dict(controles.get(original) or {})
        _remendar(entrada, campos)
        if entrada:
            controles[original] = entrada
        else:
            controles.pop(original, None)
        cru["controllers"] = controles or None
    save_profile(Profile.model_validate(cru), origem=origem or "computador-ou-jogo")


def _carregar_cru(nome: str | None) -> Profile | None:
    if not nome:
        return None
    from hefesto_dualsense4unix.profiles import loader

    try:
        return loader.load_profile(nome)
    except Exception:
        return None


def onde_grava(cartao: str, perfil: Profile | None, uniq: object = None, *,
               so_neste_jogo: bool = False) -> str:
    """``"jogo"`` ou ``"computador"``: onde um clique neste cartão grava.

    O clique grava onde a marca do cartão diz, e não onde o chip do topo aponta.
    """
    if cartao not in SECOES:
        raise KeyError(f"{cartao!r} não é um cartão do computador")
    if so_neste_jogo:
        if perfil is None:
            raise ValueError("«Só neste jogo» sem perfil ativo")
        if e_o_freestyle(perfil.name):
            raise OFreestyleNaoSobrepoeError("o Freestyle não sobrepõe nada")
        return JOGO
    return JOGO if sobrepoe(perfil, cartao, uniq) else COMPUTADOR


def gravar(
    cartao: str,
    campos: Mapping[str, Any],
    *,
    uniq: object = None,
    perfil_ativo: str | None = None,
    so_neste_jogo: bool = False,
    origem: str | None = None,
) -> str:
    """O único escritor de um cartão do computador. Devolve onde gravou.

    ``campos`` é ``{seção: {campo: valor}}`` (``None`` tira o campo), ou
    ``{seção: valor}`` para as seções que são valor inteiro. Com ``uniq``, as
    seções são as do controle; sem, as globais. Quem chama reaplica como já
    fazia.
    """
    perfil = _carregar_cru(perfil_ativo)
    onde = onde_grava(cartao, perfil, uniq, so_neste_jogo=so_neste_jogo)
    campos = _com_os_pares(campos)
    if onde == JOGO and perfil is not None:
        _no_perfil(perfil, campos, uniq, origem)
    else:
        _no_computador(campos, uniq)
    logger.info("cartao_gravado", cartao=cartao, onde=onde, perfil=perfil_ativo or "")
    return onde


def _diferenca_de_secao(secao: str, antes: Any, depois: Any) -> Any:
    """O que mudou numa seção: ``{campo: valor}``, ``None`` (tirada) ou ``{}``."""
    if secao not in _MODELOS:
        return depois if antes != depois else {}
    if depois is None:
        return None if antes is not None else {}
    novo = depois.model_dump(mode="json", exclude_unset=True)
    velho = antes.model_dump(mode="json", exclude_unset=True) if antes is not None else {}
    mudou = {c: v for c, v in novo.items() if velho.get(c, object()) != v}
    mudou.update({c: None for c in velho if c not in novo})
    return mudou


def o_que_mudou(
    cartao: str, antes: Profile, depois: Profile, uniq: object = None
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """``(globais, {identidade: seções})`` do que mudou de ``antes`` para ``depois``.

    Com ``uniq``, só a entrada daquele controle: o gesto de UM controle não leva
    ao computador a forma que a gravação deu às entradas dos outros.
    """
    secao_do_cartao = SECOES[cartao]
    globais: dict[str, Any] = {}
    if uniq is None:
        for secao in secao_do_cartao.globais:
            mudou = _diferenca_de_secao(
                secao, getattr(antes, secao, None), getattr(depois, secao, None))
            if mudou is None or mudou:
                globais[secao] = mudou
    por_controle: dict[str, dict[str, Any]] = {}
    velhos = _entradas_por_chave(antes.controllers)
    novos = _entradas_por_chave(depois.controllers)
    identidades = set(velhos) | set(novos)
    if uniq is not None:
        identidades &= {chave(uniq) or ""}
    for identidade in sorted(identidades):
        entrada_antes = (antes.controllers or {}).get(velhos.get(identidade, ""))
        entrada_depois = (depois.controllers or {}).get(novos.get(identidade, ""))
        for secao in secao_do_cartao.por_controle:
            mudou = _diferenca_de_secao(
                secao,
                getattr(entrada_antes, secao, None) if entrada_antes is not None else None,
                getattr(entrada_depois, secao, None) if entrada_depois is not None else None,
            )
            if mudou is None or mudou:
                por_controle.setdefault(identidade, {})[secao] = mudou
    return globais, por_controle


def perfil_vazio() -> Profile:
    """Um perfil que não escolhe nada: a base do computador quando não há perfil ativo."""
    return Profile.model_validate({"name": "computador", "match": {"type": "manual"}})


def gravar_pelo_gesto(
    cartao: str,
    nome: str,
    muda: Callable[[Profile], Profile | None],
    *,
    uniq: object = None,
    so_neste_jogo: bool = False,
    origem: str | None = None,
) -> tuple[str, Profile | None]:
    """O gesto de um cartão, gravado onde a marca do cartão diz.

    ``muda`` é o que o gesto sempre fez: recebe um perfil e devolve o perfil
    com a mudança (ou ``None``, quando não há o que gravar). Se o perfil
    ``nome`` sobrepõe o cartão, ``muda`` roda sobre ele e o resultado vai ao
    disco inteiro, como antes. Se não, ``muda`` roda sobre a VISTA (o que vale
    agora) e só a diferença do cartão vai ao computador; o perfil não muda.

    Sem perfil ativo (``nome`` vazio), o gesto roda sobre o computador sozinho
    e grava nele: o que é do computador não precisa de perfil.

    Levanta o que ``loader.load_profile`` e ``muda`` levantarem. Devolve
    ``(onde, perfil mudado)``.
    """
    from hefesto_dualsense4unix.profiles import loader

    cru = loader.load_profile(nome) if nome else None
    onde = onde_grava(cartao, cru, uniq, so_neste_jogo=so_neste_jogo)
    if onde == JOGO and cru is not None:
        novo = muda(cru)
        if novo is not None:
            loader.save_profile(novo, origem=origem or "computador-ou-jogo")
    else:
        vista = perfil_que_vale(cru if cru is not None else perfil_vazio(), o_computador())
        novo = muda(vista)
        if novo is not None:
            globais, por_controle = o_que_mudou(cartao, vista, novo, uniq)
            if globais:
                _no_computador(_com_os_pares(globais), None)
            for identidade, secoes in por_controle.items():
                _no_computador(_com_os_pares(secoes), identidade)
    if novo is not None:
        logger.info("cartao_gravado", cartao=cartao, onde=onde, perfil=nome)
    return onde, novo


# ---------------------------------------------------------------------------
# A migração, uma vez
# ---------------------------------------------------------------------------
#: O sufixo da cópia de cada perfil que a migração reescreve, ao lado do
#: original (a forma dos ``maquina.json.antes-de-*``).
SUFIXO_DA_COPIA = ".antes-do-computador"

#: Os atos do PS solo que a linha das Definições guardava e que são do ⑥ da
#: tabela dos gestos desde a OS-GESTOS-DO-CONTROLE-FAZEM-O-QUE-DIZEM-01.
_PS_QUE_E_DA_TABELA: frozenset[str] = frozenset({"__NADA__", "__STEAM__"})


def _sem_o_ps_da_tabela(acoes: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if acoes is None:
        return None
    return {b: a for b, a in acoes.items() if not (b == "ps" and a in _PS_QUE_E_DA_TABELA)}


def efetivo(perfil: Profile, computador: Any) -> dict[tuple[str, ...], Any]:
    """O valor que cada campo do :data:`SECOES` TEM para o aparelho. Para comparar.

    A vista põe o computador por baixo; o campo de um controle sem escolha
    própria herda a seção global do mesmo nome (é o que o aplicador faz), e
    os que não têm global (as barras dos motores, os sensores) ficam ``None``,
    que é o de fábrica deles.
    """
    vista = perfil_que_vale(perfil, computador)
    saida: dict[tuple[str, ...], Any] = {}
    for secao in ("leds", "rumble", "speaker", "mic", "mouse"):
        modelo = getattr(vista, secao, None)
        dados = modelo.model_dump(mode="json") if modelo is not None else {}
        for campo, valor in dados.items():
            saida[("global", secao, campo)] = valor
    for secao in ("button_actions", "key_bindings", "teclado_emulado"):
        saida[("global", secao)] = getattr(vista, secao, None)
    identidades = set(_entradas_por_chave(perfil.controllers)) | set(computador.controles)
    vistos = _entradas_por_chave(vista.controllers)
    for identidade in sorted(identidades):
        entrada = (vista.controllers or {}).get(vistos.get(identidade, ""))
        for secao, campos in _CAMPOS_DO_CONTROLE.items():
            proprio = getattr(entrada, secao, None) if entrada is not None else None
            escritos = proprio.model_dump(mode="json", exclude_unset=True) if proprio else {}
            do_global = getattr(vista, secao, None)
            herdado = do_global.model_dump(mode="json") if do_global is not None else {}
            for campo in campos:
                valor = escritos.get(campo)
                saida[("controle", identidade, secao, campo)] = (
                    valor if valor is not None else herdado.get(campo))
    return saida


def _escolhas(perfil: Profile) -> set[tuple[str, ...]]:
    """As chaves de :func:`efetivo` que o jogo escolheu (o que tem de sobreviver)."""
    saida: set[tuple[str, ...]] = set()
    for secao in ("leds", "rumble", "speaker", "mic", "mouse"):
        saida |= {("global", secao, c) for c in escolhas_globais_do_jogo(perfil, secao)}
    for secao in ("button_actions", "key_bindings", "teclado_emulado"):
        if escolhas_globais_do_jogo(perfil, secao):
            saida.add(("global", secao))
    for original in perfil.controllers or {}:
        identidade = chave(original)
        if identidade is None:
            continue
        for secao in _CAMPOS_DO_CONTROLE:
            saida |= {("controle", identidade, secao, c)
                      for c in escolhas_do_controle_do_jogo(perfil, original, secao)}
    return saida


def _candidatos(perfil: Profile) -> list[tuple[tuple[str, ...], ...]]:
    """O que pode sair do perfil, um grupo por vez (o par anda junto)."""
    grupos: list[tuple[tuple[str, ...], ...]] = []
    for secao in ("leds", "rumble", "speaker", "mouse"):
        escolhidos = set(escolhas_globais_do_jogo(perfil, secao))
        for par in PARES.get(secao, ()):
            if escolhidos & set(par):
                grupos.append(tuple(("global", secao, c) for c in par))
                escolhidos -= set(par)
        grupos += [(("global", secao, c),) for c in sorted(escolhidos)]
    for secao in ("button_actions", "key_bindings", "teclado_emulado"):
        if escolhas_globais_do_jogo(perfil, secao):
            grupos.append((("global", secao),))
    for original in perfil.controllers or {}:
        identidade = chave(original)
        if identidade is None:
            continue
        for secao in _CAMPOS_DO_CONTROLE:
            escolhidos = set(escolhas_do_controle_do_jogo(perfil, original, secao))
            for par in PARES.get(secao, ()):
                if escolhidos & set(par):
                    grupos.append(tuple(("controle", identidade, secao, c) for c in par))
                    escolhidos -= set(par)
            grupos += [(("controle", identidade, secao, c),) for c in sorted(escolhidos)]
    return grupos


def _sem(perfil: Profile, grupo: Iterable[tuple[str, ...]]) -> Profile:
    """O perfil sem os campos do grupo (``None`` é «sem opinião» no esquema)."""
    cru: dict[str, Any] = perfil.model_dump(mode="json", exclude_unset=True)
    for chave_ in grupo:
        if chave_[0] == "global" and len(chave_) == 2:
            cru.pop(chave_[1], None)
        elif chave_[0] == "global":
            _, secao, campo = chave_
            atual = dict(cru.get(secao) or {})
            if secao in _DENSAS and campo in _DENSAS[secao]:
                atual[campo] = _DENSAS[secao][campo]
            else:
                atual.pop(campo, None)
            if atual:
                cru[secao] = atual
            else:
                cru.pop(secao, None)
        else:
            _, identidade, secao, campo = chave_
            controles = dict(cru.get("controllers") or {})
            original = _entradas_por_chave(controles).get(identidade)
            if original is None:
                continue
            entrada = dict(controles[original])
            atual = dict(entrada.get(secao) or {})
            atual.pop(campo, None)
            if atual:
                entrada[secao] = atual
            else:
                entrada.pop(secao, None)
            if entrada:
                controles[original] = entrada
            else:
                controles.pop(original)
            cru["controllers"] = controles or None
    return Profile.model_validate(cru)


def ceder_ao_computador(perfil: Profile, computador: Any) -> tuple[Profile, int]:
    """O perfil sem o que já vale igual pelo computador. Devolve ``(perfil, saíram)``.

    Um grupo (o campo, ou o par) só sai se, sem ele, NENHUM valor efetivo
    deste perfil muda com este computador (:func:`efetivo`, campo a campo, em
    todo controle): a régua é o valor que o aparelho recebe, e não o campo que
    sai. O Freestyle não sobrepõe nada, e perde o que o computador guarda
    (o computador nasceu dele); o microfone global fica, porque o computador
    não guarda microfone global.
    """
    if e_o_freestyle(perfil.name):
        cru = perfil.model_dump(mode="json", exclude_unset=True)
        saiu = 0
        for secao in ("leds", "rumble", "speaker", "button_actions", "key_bindings",
                      "teclado_emulado"):
            saiu += secao in cru
            cru.pop(secao, None)
        if isinstance(cru.get("mouse"), dict):
            saiu += sum(c in cru["mouse"] for c in ("speed", "scroll_speed"))
            cru["mouse"] = {k: v for k, v in cru["mouse"].items()
                            if k not in ("speed", "scroll_speed")}
        controles = {}
        for original, entrada in dict(cru.get("controllers") or {}).items():
            resto = {s: v for s, v in dict(entrada).items() if s not in _CAMPOS_DO_CONTROLE}
            saiu += len(dict(entrada)) - len(resto)
            if resto:
                controles[original] = resto
        cru["controllers"] = controles or None
        return Profile.model_validate(cru), saiu
    antes = efetivo(perfil, computador)
    atual = perfil
    saiu = 0
    for grupo in _candidatos(perfil):
        tentativa = _sem(atual, grupo)
        if efetivo(tentativa, computador) == antes:
            atual = tentativa
            saiu += len(grupo)
    return atual, saiu


def semente_do_freestyle(freestyle: Profile | None) -> dict[str, Any]:
    """O documento do computador que nasce do Freestyle (o que ele escreveu).

    Sem Freestyle, só as velocidades do ``mouse_emulation.flag``.
    """
    do_global: dict[str, Any] = {}
    controles: dict[str, Any] = {}
    if freestyle is not None:
        for secao in ("leds", "rumble", "speaker"):
            modelo = getattr(freestyle, secao, None)
            if modelo is None or secao not in freestyle.model_fields_set:
                continue
            dados = modelo.model_dump(mode="json", exclude_unset=True)
            fabrica = _DENSAS.get(secao, {})
            escolhidos = {c for c, v in dados.items()
                          if v is not None and (c not in fabrica or v != fabrica[c])}
            escolhidos = _expandir_pares(secao, escolhidos)
            if escolhidos:
                do_global[secao] = {c: dados.get(c) for c in escolhidos}
        mouse = freestyle.mouse
        if mouse is not None:
            do_global["mouse"] = {"speed": mouse.speed, "scroll_speed": mouse.scroll_speed}
        acoes = _sem_o_ps_da_tabela(freestyle.button_actions)
        if acoes:
            do_global["button_actions"] = acoes
        if freestyle.key_bindings is not None:
            do_global["key_bindings"] = freestyle.key_bindings
        if freestyle.teclado_emulado is not None:
            do_global["teclado_emulado"] = freestyle.teclado_emulado
        for original, entrada in (freestyle.controllers or {}).items():
            identidade = chave(original)
            if identidade is None:
                continue
            dados_entrada = {
                secao: {c: v for c, v in valor.model_dump(mode="json",
                                                           exclude_unset=True).items()
                        if v is not None}
                for secao in _CAMPOS_DO_CONTROLE
                if (valor := getattr(entrada, secao, None)) is not None
            }
            dados_entrada = {s: v for s, v in dados_entrada.items() if v}
            if dados_entrada:
                controles[identidade] = dados_entrada
    if "mouse" not in do_global:
        # Sem Freestyle (ou sem a seção dele), as velocidades de agora.
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import load_mouse_preference

            _ligada, speed, scroll = load_mouse_preference()
            mouse_ = {c: v for c, v in (("speed", speed), ("scroll_speed", scroll))
                      if v is not None}
            if mouse_:
                do_global["mouse"] = mouse_
    documento: dict[str, Any] = {}
    if do_global:
        documento["global"] = do_global
    if controles:
        documento["controles"] = controles
    return documento


def _por_baixo(existente: dict[str, Any], semente: Mapping[str, Any]) -> dict[str, Any]:
    """A semente só onde o computador ainda não diz nada (um clique já dado vence)."""
    saida = dict(existente)
    for chave_, valor in semente.items():
        if isinstance(valor, Mapping) and isinstance(saida.get(chave_), Mapping):
            saida[chave_] = _por_baixo(dict(saida[chave_]), valor)
        elif chave_ not in saida or saida[chave_] is None:
            saida[chave_] = valor
    return saida


def _contar(semente: Mapping[str, Any]) -> int:
    """Quantos campos a semente leva (o número do diário)."""
    total = 0
    for valor in (semente.get("global") or {}).values():
        total += len(valor) if isinstance(valor, Mapping) else 1
    for entrada in (semente.get("controles") or {}).values():
        total += sum(len(v) for v in entrada.values())
    return total


def migrar_uma_vez() -> dict[str, int] | None:
    """O computador nasce do Freestyle, e cada perfil perde o que já vale igual.

    Uma vez: a marca é ``computador.migrado`` no ``maquina.json``. Cada perfil
    reescrito ganha antes a cópia ``<perfil>.json.antes-do-computador`` ao
    lado (e a versão do ``.historico``, que o ``save_profile`` guarda). Perfil
    que é cópia intocada de fábrica não é reescrito: a atualização da fábrica
    continua o alcançando. Devolve ``{perfil: campos que saíram}``, ou ``None``
    quando não rodou.
    """
    from pathlib import Path

    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.utils.maquina import gravar_o_computador
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    computador = o_computador()
    if computador.migrado:
        return None
    pasta = profiles_dir(ensure=True)
    perfis: list[tuple[Path, Profile, dict[str, Any]]] = []
    for caminho in sorted(pasta.glob("*.json")):
        dados = loader._dados_crus_do_perfil(caminho)
        if dados is None:
            continue
        try:
            perfis.append((caminho, Profile.model_validate(dados), dados))
        except Exception:
            logger.warning("computador_pulou_perfil_torto", arquivo=caminho.name)
    freestyle = next((p for _c, p, _d in perfis if e_o_freestyle(p.name)), None)
    semente = semente_do_freestyle(freestyle)
    documento = _por_baixo(computador.model_dump(mode="json"), semente)
    if not gravar_o_computador(documento):
        logger.warning("computador_nao_semeado")
        return None
    computador = o_computador()
    logger.info("computador_semeado", de="freestyle" if freestyle else "mouse_emulation",
                campos=_contar(semente))
    saidas: dict[str, int] = {}
    for caminho, perfil, dados in perfis:
        if loader._e_copia_de_fabrica(caminho, dados):
            continue
        try:
            novo, saiu = ceder_ao_computador(perfil, computador)
        except Exception as exc:
            logger.warning("perfil_nao_cedeu_ao_computador", perfil=perfil.name,
                           err=str(exc)[:200])
            continue
        acoes = novo.button_actions
        if acoes is not None and acoes.get("ps") in _PS_QUE_E_DA_TABELA:
            novo = novo.model_copy(update={"button_actions": _sem_o_ps_da_tabela(acoes) or None})
            saiu += 1
            logger.info("ps_do_perfil_foi_para_a_tabela", perfil=perfil.name)
        if not saiu:
            continue
        if loader._profile_path(novo) != caminho:
            # O nome não dá este arquivo: gravar criaria um segundo perfil.
            logger.warning("perfil_nao_cedeu_ao_computador", perfil=perfil.name,
                           err="o nome do perfil não é o do arquivo")
            continue
        copia = caminho.with_name(caminho.name + SUFIXO_DA_COPIA)
        try:
            if not copia.exists():
                copia.write_bytes(caminho.read_bytes())
            loader.save_profile(novo, origem="migracao-do-computador")
        except (OSError, ValueError) as exc:
            logger.warning("perfil_nao_cedeu_ao_computador", perfil=perfil.name,
                           err=str(exc)[:200])
            continue
        saidas[perfil.name] = saiu
        logger.info("perfil_cedeu_ao_computador", perfil=perfil.name, campos=saiu,
                    ficaram=len(_escolhas(novo)))
    documento = o_computador().model_dump(mode="json")
    documento["migrado"] = True
    gravar_o_computador(documento)
    return saidas


# ---------------------------------------------------------------------------
# Os três gestos do cartão
# ---------------------------------------------------------------------------
def _identidades(perfil: Profile, uniq: object) -> list[str]:
    if uniq is not None:
        identidade = chave(uniq)
        return [identidade] if identidade else []
    return sorted(_entradas_por_chave(perfil.controllers))


#: O que vale num controle sem entrada própria, quando a vista também não tem a
#: seção global: os sensores nascem ligados (a regra do interruptor da aba
#: Controles), e o ``None`` do perfil é «não mexer», não «ligado».
_DE_FABRICA_NO_CONTROLE: dict[str, dict[str, Any]] = {
    "sensores": {"giroscopio": True, "acelerometro": True},
}


def _o_que_vale_no_controle_sem_entrada(vista: Profile, nome: str) -> dict[str, Any]:
    """A seção ``nome`` de um controle sem entrada própria, na forma da seção por controle.

    Sem entrada, o controle vale a seção GLOBAL da vista (a luz, o som, a
    força da vibração), e o que ela não tem vale o de fábrica (os sensores). O
    «Só neste jogo» de UM controle copia esse valor para a entrada dele, com os
    campos escritos: uma entrada vazia não é escolha, e o clique não faria
    nada. Só entram os campos que a seção por controle conhece (a da vibração
    é um pedaço da global). O microfone não se copia: o mudo é do controle
    (O-MUDO-E-DO-CONTROLE-01), e o volume sem opinião é silêncio.
    """
    from pydantic import BaseModel

    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    if nome == "mic":
        return {}
    global_ = getattr(vista, nome, None)
    if isinstance(global_, BaseModel):
        anotacao = ControllerOverrides.model_fields[nome].annotation
        campos = {c for a in getattr(anotacao, "__args__", (anotacao,))
                  if isinstance(a, type) and issubclass(a, BaseModel)
                  for c in a.model_fields}
        return {k: v for k, v in global_.model_dump(mode="json").items()
                if k in campos and v is not None}
    return dict(_DE_FABRICA_NO_CONTROLE.get(nome, {}))


def perfil_so_neste_jogo(
    cartao: str,
    uniq: object,
    cru_perfil: Profile,
    computador: Any,
    vivos: Mapping[str, Any] | None = None,
) -> Profile:
    """O perfil depois do «Só neste jogo», em memória: o disco não muda.

    Copia o que vale agora no cartão. Com ``uniq``, só aquele controle; sem, as
    seções globais e todo controle que o computador ou o perfil conhecem.

    ``vivos`` é ``{seção: valor}`` do que o aparelho tem AGORA, lido pela tela
    (o volume do alto-falante daquele controle, a força da mesa, as
    velocidades do mouse e o teclado ligado). É o último degrau de «o que vale
    agora»: quando nem o jogo nem o computador declaram a seção, o que vale é
    o que está no aparelho. Sem ele, o «Só neste jogo» do som, da vibração, do
    mouse e do teclado não copiava nada num computador ainda sem padrão, e o
    clique passava sem efeito (medido na conferência de 02/10/2026).
    """
    vista = perfil_que_vale(cru_perfil, computador)
    secao = SECOES[cartao]
    vivos = vivos or {}
    cru = cru_perfil.model_dump(mode="json", exclude_unset=True)
    if uniq is None:
        for nome in secao.globais:
            valor = getattr(vista, nome, None)
            if valor is not None:
                cru[nome] = valor.model_dump(mode="json") if nome in _MODELOS else valor
            elif nome in vivos and vivos[nome] is not None:
                cru[nome] = vivos[nome]
    identidades = _identidades(vista, uniq)
    if uniq is None:
        identidades = sorted(set(identidades) | set(computador.controles))
    if secao.por_controle and identidades:
        controles = dict(cru.get("controllers") or {})
        originais = _entradas_por_chave(controles)
        vistos = _entradas_por_chave(vista.controllers)
        for identidade in identidades:
            entrada_vista = (vista.controllers or {}).get(vistos.get(identidade, ""))
            original = originais.get(identidade, identidade)
            entrada = dict(controles.get(original) or {})
            for nome in secao.por_controle:
                valor = getattr(entrada_vista, nome, None) if entrada_vista else None
                if valor is not None:
                    entrada[nome] = valor.model_dump(mode="json", exclude_unset=True)
                elif uniq is not None and nome not in entrada:
                    copia = (_o_que_vale_no_controle_sem_entrada(vista, nome)
                             or dict(vivos.get(nome) or {}))
                    if copia:
                        entrada[nome] = copia
            if entrada:
                controles[original] = entrada
        cru["controllers"] = controles or None
    return Profile.model_validate(cru)


def pode_so_neste_jogo(
    cartao: str,
    uniq: object,
    cru_perfil: Profile | None,
    computador: Any = None,
    vivos: Mapping[str, Any] | None = None,
) -> bool:
    """O «Só neste jogo» daria ao jogo escolha própria neste cartão?

    É a pergunta da marca antes de oferecer o botão: um botão que aceita o
    clique e não muda nada é o defeito que *«tudo na interface deveria
    funcionar»* proíbe. Não é o caso quando o que vale agora é o de fábrica de
    uma seção densa (as velocidades do mouse em 6 e 1, por exemplo): o
    esquema não distingue «o jogo escolheu o de fábrica» de «ninguém
    escolheu». Nunca levanta: é pintura de tique.
    """
    if cru_perfil is None or e_o_freestyle(cru_perfil.name):
        return False
    try:
        novo = perfil_so_neste_jogo(
            cartao, uniq, cru_perfil,
            computador if computador is not None else o_computador(), vivos)
    except Exception:
        return False
    return sobrepoe(novo, cartao, uniq)


def so_neste_jogo(
    cartao: str, uniq: object, perfil: str, vivos: Mapping[str, Any] | None = None
) -> Profile:
    """Copia para o perfil o que vale agora no cartão. Daí em diante, o jogo manda.

    Grava só quando a cópia dá ao jogo escolha própria no cartão; se não daria,
    recusa sem gravar (:class:`OJogoNaoTeriaOQueGuardarError`).
    """
    from hefesto_dualsense4unix.profiles.loader import save_profile

    if e_o_freestyle(perfil):
        raise OFreestyleNaoSobrepoeError("o Freestyle não sobrepõe nada")
    from hefesto_dualsense4unix.profiles import loader

    novo = perfil_so_neste_jogo(cartao, uniq, loader.load_profile(perfil), o_computador(),
                                vivos)
    if not sobrepoe(novo, cartao, uniq):
        raise OJogoNaoTeriaOQueGuardarError(
            "este cartão está no de fábrica: o jogo não teria o que guardar.")
    save_profile(novo, origem="so-neste-jogo")
    logger.info("cartao_so_neste_jogo", cartao=cartao, perfil=perfil, uniq=str(uniq or ""))
    return novo


def voltar_ao_do_computador(cartao: str, uniq: object, perfil: str) -> Profile:
    """Tira do perfil o que ele escolheu neste cartão: volta a valer o computador.

    Com ``uniq``, a seção daquele controle e as globais do cartão (a escolha
    global do jogo também vence o computador naquele controle); sem, o cartão
    inteiro, em todo controle.
    """
    from hefesto_dualsense4unix.profiles import loader

    cru_perfil = loader.load_profile(perfil)
    secao = SECOES[cartao]
    cru = cru_perfil.model_dump(mode="json", exclude_unset=True)
    for nome in secao.globais:
        if nome in _DENSAS and nome != "mouse":
            cru[nome] = dict(_DENSAS[nome])
        elif nome == "mouse":
            if cru.get("mouse"):
                cru["mouse"] = {**cru["mouse"], **_DENSAS["mouse"]}
        elif nome == "mic" and cru.get("mic"):
            # O modo do microfone fica: tem dono próprio (`JA_DO_COMPUTADOR`).
            cru["mic"] = {"button_toggles_system": cru["mic"].get("button_toggles_system")}
        else:
            cru.pop(nome, None)
    if secao.por_controle:
        controles = dict(cru.get("controllers") or {})
        alvo = set(_identidades(cru_perfil, uniq))
        for identidade, original in _entradas_por_chave(controles).items():
            if identidade not in alvo:
                continue
            entrada = {k: v for k, v in dict(controles[original]).items()
                       if k not in secao.por_controle}
            if entrada:
                controles[original] = entrada
            else:
                controles.pop(original)
        cru["controllers"] = controles or None
    novo = Profile.model_validate(cru)
    loader.save_profile(novo, origem="voltar-ao-do-computador")
    logger.info("cartao_voltou_ao_computador", cartao=cartao, perfil=perfil,
                uniq=str(uniq or ""))
    return novo


def voltar_o_computador_ao_de_fabrica(cartao: str, uniq: object = None) -> None:
    """O cartão do computador volta ao de fábrica (o degrau de baixo do «Voltar»)."""
    secao = SECOES[cartao]
    if uniq is None:
        _no_computador({nome: None for nome in secao.no_computador}, None)
        identidades = sorted(o_computador().controles)
    else:
        identidade = chave(uniq)
        identidades = [identidade] if identidade else []
    for identidade in identidades:
        _no_computador({nome: None for nome in secao.por_controle}, identidade)
    logger.info("cartao_do_computador_de_fabrica", cartao=cartao, uniq=str(uniq or ""))


def restaurar_o_computador() -> bool:
    """Esvazia o padrão do computador. A marca da migração fica: ela não volta."""
    from hefesto_dualsense4unix.utils.maquina import gravar_o_computador

    migrado = o_computador().migrado
    feito = gravar_o_computador({"migrado": True} if migrado else {})
    if feito:
        logger.info("computador_de_fabrica")
    else:
        logger.warning("computador_nao_voltou_ao_de_fabrica")
    return feito


def marca(cartao: str, perfil: Profile | None, uniq: object = None) -> str:
    """O que o cabeçalho do cartão diz: «Computador» ou o nome do jogo."""
    if perfil is not None and sobrepoe(perfil, cartao, uniq):
        return perfil.name
    return "Computador"


__all__ = [
    "COMPUTADOR",
    "DO_JOGO",
    "JA_DO_COMPUTADOR",
    "JOGO",
    "PARES",
    "SECOES",
    "SUFIXO_DA_COPIA",
    "OFreestyleNaoSobrepoeError",
    "OJogoNaoTeriaOQueGuardarError",
    "Secao",
    "carregar_o_que_vale",
    "ceder_ao_computador",
    "chave",
    "chave_no_perfil",
    "computador_vazio",
    "e_o_freestyle",
    "efetivo",
    "escolhas_do_controle_do_jogo",
    "escolhas_globais_do_jogo",
    "gravar",
    "gravar_pelo_gesto",
    "marca",
    "migrar_uma_vez",
    "o_computador",
    "o_que_mudou",
    "o_que_vale",
    "onde_grava",
    "perfil_que_vale",
    "perfil_so_neste_jogo",
    "perfil_vazio",
    "pode_so_neste_jogo",
    "restaurar_o_computador",
    "selo_da_maquina",
    "semente_do_freestyle",
    "so_neste_jogo",
    "sobrepoe",
    "velocidades_do_computador",
    "voltar_ao_do_computador",
    "voltar_o_computador_ao_de_fabrica",
]
