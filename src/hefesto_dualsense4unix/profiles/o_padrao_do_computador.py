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
- :func:`gravar` e :func:`gravar_a_mudanca`: o único escritor de um cartão do
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
from collections.abc import Iterable, Mapping
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
    if do_global.button_actions is not None:
        cru["button_actions"] = {**do_global.button_actions, **(perfil.button_actions or {})}
    if do_global.key_bindings is not None and perfil.key_bindings != {}:
        cru["key_bindings"] = {**do_global.key_bindings, **(perfil.key_bindings or {})}
    if do_global.teclado_emulado is not None and perfil.teclado_emulado is None:
        cru["teclado_emulado"] = do_global.teclado_emulado
    if computador.controles:
        cru["controllers"] = _controles_que_valem(perfil, cru.get("controllers"), computador)
    return Profile.model_validate(cru)


def _controles_que_valem(
    perfil: Profile, do_jogo: Mapping[str, Any] | None, computador: Any
) -> dict[str, Any]:
    entradas: dict[str, Any] = {k: dict(v) for k, v in (do_jogo or {}).items()}
    originais = _entradas_por_chave(entradas)
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
            escritos = {c for c, v in do_controle.items() if v is not None}
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
        _remendar(do_global, {s: v for s, v in campos.items() if s in _GLOBAIS_DO_COMPUTADOR})
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


def o_que_mudou(cartao: str, antes: Profile, depois: Profile) -> tuple[
    dict[str, Any], dict[str, dict[str, Any]]
]:
    """``(globais, {identidade: seções})`` do que mudou de ``antes`` para ``depois``."""
    secao_do_cartao = SECOES[cartao]
    globais: dict[str, Any] = {}
    for secao in secao_do_cartao.globais:
        mudou = _diferenca_de_secao(
            secao, getattr(antes, secao, None), getattr(depois, secao, None))
        if mudou is None or mudou:
            globais[secao] = mudou
    por_controle: dict[str, dict[str, Any]] = {}
    velhos = _entradas_por_chave(antes.controllers)
    novos = _entradas_por_chave(depois.controllers)
    for identidade in sorted(set(velhos) | set(novos)):
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


def gravar_a_mudanca(
    cartao: str,
    antes: Profile,
    depois: Profile,
    *,
    uniq: object = None,
    so_neste_jogo: bool = False,
    origem: str | None = None,
) -> str:
    """O que o gesto mudou no perfil (``antes`` → ``depois``), gravado onde vale.

    Os gestos montam o perfil novo como sempre montaram. Se o perfil sobrepõe o
    cartão, o ``depois`` vai ao disco inteiro, como antes; se não, só a
    diferença do cartão vai ao computador, e o perfil fica como estava.
    """
    onde = onde_grava(cartao, antes, uniq, so_neste_jogo=so_neste_jogo)
    if onde == JOGO:
        from hefesto_dualsense4unix.profiles.loader import save_profile

        save_profile(depois, origem=origem or "computador-ou-jogo")
    else:
        globais, por_controle = o_que_mudou(cartao, antes, depois)
        if globais:
            _no_computador(_com_os_pares(globais), None)
        for identidade, secoes in por_controle.items():
            _no_computador(_com_os_pares(secoes), identidade)
    logger.info("cartao_gravado", cartao=cartao, onde=onde, perfil=antes.name)
    return onde


# ---------------------------------------------------------------------------
# Os três gestos do cartão
# ---------------------------------------------------------------------------
def _identidades(perfil: Profile, uniq: object) -> list[str]:
    if uniq is not None:
        identidade = chave(uniq)
        return [identidade] if identidade else []
    return sorted(_entradas_por_chave(perfil.controllers))


def so_neste_jogo(cartao: str, uniq: object, perfil: str) -> Profile:
    """Copia para o perfil o que vale agora no cartão. Daí em diante, o jogo manda.

    Com ``uniq``, só aquele controle; sem, as seções globais e todo controle que
    o computador ou o perfil conhecem.
    """
    from hefesto_dualsense4unix.profiles.loader import save_profile

    if e_o_freestyle(perfil):
        raise OFreestyleNaoSobrepoeError("o Freestyle não sobrepõe nada")
    from hefesto_dualsense4unix.profiles import loader

    cru_perfil = loader.load_profile(perfil)
    computador = o_computador()
    vista = perfil_que_vale(cru_perfil, computador)
    secao = SECOES[cartao]
    cru = cru_perfil.model_dump(mode="json", exclude_unset=True)
    if uniq is None:
        for nome in secao.globais:
            valor = getattr(vista, nome, None)
            if valor is None:
                continue
            cru[nome] = valor.model_dump(mode="json") if nome in _MODELOS else valor
    identidades = _identidades(vista, uniq)
    if uniq is None:
        identidades = sorted(set(identidades) | set(computador.controles))
    if secao.por_controle and identidades:
        controles = dict(cru.get("controllers") or {})
        originais = _entradas_por_chave(controles)
        vistos = _entradas_por_chave(vista.controllers)
        for identidade in identidades:
            entrada_vista = (vista.controllers or {}).get(vistos.get(identidade, ""))
            if entrada_vista is None:
                continue
            original = originais.get(identidade, identidade)
            entrada = dict(controles.get(original) or {})
            for nome in secao.por_controle:
                valor = getattr(entrada_vista, nome, None)
                if valor is not None:
                    entrada[nome] = valor.model_dump(mode="json", exclude_unset=True)
            if entrada:
                controles[original] = entrada
        cru["controllers"] = controles or None
    novo = Profile.model_validate(cru)
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
    return gravar_o_computador({"migrado": True} if migrado else {})


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
    "OFreestyleNaoSobrepoeError",
    "Secao",
    "carregar_o_que_vale",
    "chave",
    "computador_vazio",
    "e_o_freestyle",
    "escolhas_do_controle_do_jogo",
    "escolhas_globais_do_jogo",
    "gravar",
    "gravar_a_mudanca",
    "marca",
    "o_computador",
    "o_que_mudou",
    "o_que_vale",
    "onde_grava",
    "perfil_que_vale",
    "restaurar_o_computador",
    "selo_da_maquina",
    "so_neste_jogo",
    "sobrepoe",
    "velocidades_do_computador",
    "voltar_ao_do_computador",
    "voltar_o_computador_ao_de_fabrica",
]
