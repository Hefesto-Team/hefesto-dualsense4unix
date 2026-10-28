"""O padrão do computador: o que não muda com o jogo, e o perfil que só sobrepõe."""
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
    ProfileAnalogicosConfig,
    ProfileAtivacaoConfig,
    ProfileCursorConfig,
    ProfileMouseConfig,
    ProfileSpeakerConfig,
    RumbleConfig,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import CAMPOS_DO_CONTROLE_NO_COMPUTADOR

logger = get_logger(__name__)


class Secao(NamedTuple):
    """Um cartão da tela cujo valor é do computador."""

    cartao: str
    pagina: str
    rotulo: str
    globais: tuple[str, ...]
    no_computador: tuple[str, ...]
    por_controle: tuple[str, ...]


_DA_ACESSIBILIDADE = ("ativacao", "analogicos")  # (noqa-acento)
_GLOBAIS_DA_ACESSIBILIDADE = (*_DA_ACESSIBILIDADE, "cursor")

_CAMPOS_DO_TECLADO = ("teclado_emulado", "teclado_so_no_jogo", "teclado_sempre", "key_bindings")

SECOES: dict[str, Secao] = {
    "som": Secao("som", "02-controles.html", "Som",
                 ("speaker", "mic"), ("speaker",), ("speaker", "mic")),
    "sensores": Secao("sensores", "02-controles.html", "Sensores",
                      (), (), ("sensores",)),
    "luz": Secao("luz", "04-iluminacao.html", "Luz",
                 ("leds",), ("leds",), ("leds",)),
    "vibracao": Secao("vibracao", "05-vibracao.html", "Vibração",
                      ("rumble",), ("rumble",), ("rumble",)),
    "gatilho": Secao("gatilho", "03-gatilhos.html", "Intensidade do gatilho",
                     (), (), ("triggers",)),
    "mouse": Secao("mouse", "06-navegacao.html", "Mouse",
                   ("mouse", "button_actions", "tabela_no_jogo"),
                   ("mouse", "button_actions", "tabela_no_jogo"), ()),
    "teclado": Secao("teclado", "06-navegacao.html", "Teclado",
                     _CAMPOS_DO_TECLADO, _CAMPOS_DO_TECLADO, ()),
    "acessibilidade": Secao("acessibilidade", "06-navegacao.html", "Acessibilidade",
                            _GLOBAIS_DA_ACESSIBILIDADE, _GLOBAIS_DA_ACESSIBILIDADE,
                            _DA_ACESSIBILIDADE),
}

DO_JOGO: dict[str, str] = {
    "mode": "o modo (Sony, Xbox, Navegação, Nativo) é de cada jogo",
    "movimento": "a Mira é do jogo que mira",
    "triggers": "o efeito do gatilho é de cada jogo; a intensidade é do computador",
    "remapeamento": "a troca de botões é do jogo",
    "mouse.enabled": "o Point-and-click liga com o jogo de mouse",
    "suppress_desktop_emulation": "o modo-jogo é de cada jogo",
}

JA_DO_COMPUTADOR: dict[str, str] = {
    "mic.button_toggles_system": "D-O-MICROFONE-A-MAQUINA-DA-O-PADRAO-O-PERFIL-SOBREPOE",
}

PARES: dict[str, tuple[tuple[str, ...], ...]] = {
    "rumble": (("policy", "custom_mult"),),
    "leds": (("lightbar", "lightbar_para_o_numero"),),
}

_DENSAS: dict[str, dict[str, Any]] = {
    "leds": LedsConfig().model_dump(mode="json"),
    "rumble": RumbleConfig().model_dump(mode="json"),
    "mouse": {
        campo: ProfileMouseConfig.model_fields[campo].default
        for campo in ("speed", "scroll_speed", "point_and_click")
    },
}

_MODELOS: frozenset[str] = frozenset(
    {"leds", "rumble", "speaker", "mic", "sensores", "mouse", "triggers",
     *_GLOBAIS_DA_ACESSIBILIDADE}
)

_MODELO_DA_ACESSIBILIDADE: dict[str, Any] = {
    "ativacao": ProfileAtivacaoConfig,  # (noqa-acento)
    "analogicos": ProfileAnalogicosConfig,
    "cursor": ProfileCursorConfig,
}

_CAMPOS_DO_CONTROLE: dict[str, tuple[str, ...]] = {
    "leds": tuple(LedsConfig.model_fields),
    "speaker": tuple(ProfileSpeakerConfig.model_fields),
    "mic": tuple(ControllerMicOverride.model_fields),
    "rumble": tuple(ControllerRumbleOverride.model_fields),
    "sensores": tuple(ControllerSensoresOverride.model_fields),
    "ativacao": tuple(ProfileAtivacaoConfig.model_fields),  # (noqa-acento)
    "analogicos": tuple(ProfileAnalogicosConfig.model_fields),
    **CAMPOS_DO_CONTROLE_NO_COMPUTADOR,
}


def _so_a_parte_do_computador(secao: str, dados: Mapping[str, Any]) -> dict[str, Any]:
    """Os campos de ``secao`` que são do computador (do gatilho, só a intensidade)."""
    so_estes = CAMPOS_DO_CONTROLE_NO_COMPUTADOR.get(secao)
    return dict(dados) if so_estes is None else {c: v for c, v in dados.items() if c in so_estes}


def _sem_a_parte_do_computador(secao: str, dados: Any) -> Any:
    """O que fica de ``secao`` no jogo quando a parte do computador sai (``None``: nada fica)."""
    so_estes = CAMPOS_DO_CONTROLE_NO_COMPUTADOR.get(secao)
    if so_estes is None or not isinstance(dados, Mapping):
        return None
    resto = {c: v for c, v in dados.items() if c not in so_estes}
    return resto or None

COMPUTADOR = "computador"
JOGO = "jogo"


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
    """A chave da entrada deste controle como o perfil a escreveu."""
    identidade = chave(uniq)
    original = _entradas_por_chave(perfil.controllers).get(identidade or "")
    return original or identidade or str(uniq)


def e_o_freestyle(nome: object) -> bool:
    """O Freestyle é o perfil de fora do jogo: ele não sobrepõe nada."""
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
        escolhidos &= {"speed", "scroll_speed", "point_and_click"}
    if secao == "mic":
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
    dados = _so_a_parte_do_computador(secao, valor.model_dump(mode="json", exclude_unset=True))
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


def computador_vazio(computador: Any) -> bool:
    """O computador não declarou nada (a vista devolve o próprio perfil)."""
    if computador is None:
        return True
    return not computador.controles and not computador.global_.model_dump(
        exclude_unset=True, exclude_none=True)


def perfil_que_vale(perfil: Profile, computador: Any) -> Profile:
    """O perfil com o computador por baixo, na precedência do cabeçalho."""
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
            continue
        escolhas = escolhas_globais_do_jogo(perfil, secao)
        atual = dict(cru.get(secao) or {})
        for campo, valor in do_computador.items():
            if campo not in escolhas:
                atual[campo] = valor
        cru[secao] = atual
    freestyle = e_o_freestyle(perfil.name)
    for secao in _GLOBAIS_DA_ACESSIBILIDADE:
        modelo = getattr(do_global, secao, None)
        if modelo is None:
            continue
        juntado = _secao_que_vale(
            secao, modelo.model_dump(mode="json", exclude_unset=True),
            cru.get(secao) or {}, freestyle)
        if juntado:
            cru[secao] = juntado
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
    for escalar in ("teclado_so_no_jogo", "teclado_sempre", "tabela_no_jogo"):
        valor = getattr(do_global, escalar)
        if valor is not None and (freestyle or getattr(perfil, escalar) is None):
            cru[escalar] = valor
    if computador.controles:
        cru["controllers"] = _controles_que_valem(perfil, cru.get("controllers"), computador)
    return Profile.model_validate(cru)


def _secao_que_vale(
    secao: str, do_computador: Mapping[str, Any], do_jogo: Mapping[str, Any], freestyle: bool
) -> dict[str, Any]:
    """O computador por baixo, o jogo por cima; o conflito entre os dois fica com o jogo.

    Um botão tem um modo só e a mão decide a troca: se a soma dos dois quebra isso, vale o que o
    jogo escreveu (o Freestyle não sobrepõe nada: vale o computador).
    """
    ordem = (do_computador, do_jogo) if not freestyle else (do_jogo, do_computador)
    juntado = {**ordem[0], **ordem[1]}
    try:
        _MODELO_DA_ACESSIBILIDADE[secao].model_validate(juntado)
    except ValueError:
        return dict(do_jogo) if not freestyle else dict(do_computador)
    return juntado


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
            campos = _so_a_parte_do_computador(secao, campos)
            do_controle = dict(entrada.get(secao) or {})
            do_jogo_na_peca = dict(do_controle)
            escritos = set() if freestyle else {
                c for c, v in do_controle.items() if v is not None}
            escolhidos = _expandir_pares(secao, escritos | globais.get(secao, set()))
            for campo, valor in campos.items():
                if campo not in escolhidos:
                    do_controle[campo] = valor
            if secao in _DA_ACESSIBILIDADE:
                do_controle = _secao_que_vale(
                    secao,
                    {c: v for c, v in campos.items() if c not in escolhidos},
                    {c: v for c, v in do_jogo_na_peca.items() if v is not None}, freestyle)
            if do_controle:
                entrada[secao] = do_controle
        if entrada:
            entradas[original] = entrada
    return entradas


def carregar_o_que_vale(nome: str) -> Profile:
    """``load_profile`` com o computador por baixo. É a leitura de quem APLICA."""
    from hefesto_dualsense4unix.profiles import loader

    return o_que_vale(loader.load_profile(nome))


def o_que_vale(perfil: Profile) -> Profile:
    """:func:`perfil_que_vale` com o computador do disco. Para quem já leu o perfil."""
    return perfil_que_vale(perfil, o_computador())


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
        _remendar(entrada, {
            s: (_so_a_parte_do_computador(s, v) if isinstance(v, Mapping) else v)
            for s, v in campos.items() if s in _CAMPOS_DO_CONTROLE})
        if entrada:
            controles[identidade] = entrada
        else:
            controles.pop(identidade, None)
        documento["controles"] = controles
    if not gravar_o_computador(documento):
        raise OSError("o maquina.json é de outra versão e não foi regravado")
    return documento


_CAMPOS_DO_GLOBAL: dict[str, tuple[str, ...]] = {
    "mouse": ("speed", "scroll_speed", "point_and_click")}


def _so_os_campos_do_computador(secao: str, valor: Mapping[str, Any]) -> dict[str, Any]:
    campos = _CAMPOS_DO_GLOBAL.get(secao)
    return dict(valor) if campos is None else {c: v for c, v in valor.items() if c in campos}


_GLOBAIS_DO_COMPUTADOR: frozenset[str] = frozenset(
    s for secao in SECOES.values() for s in secao.no_computador
)


def _no_perfil(perfil: Profile, campos: Mapping[str, Any], uniq: object,
               origem: str | None) -> None:
    """Os ``campos`` de UM lugar (o global, ou o controle ``uniq``) no perfil do jogo."""
    por_controle: dict[str, dict[str, Any]] = {}
    if uniq is not None:
        por_controle = {chave(uniq) or str(uniq): dict(campos)}
    _no_perfil_so_o_que_mudou(perfil, dict(campos) if uniq is None else {}, por_controle,
                              origem)


def _no_perfil_so_o_que_mudou(perfil: Profile, globais: Mapping[str, Any],
                              por_controle: Mapping[str, Mapping[str, Any]],
                              origem: str | None) -> None:
    """Só o que mudou vai ao perfil do jogo; o resto do cartão segue vindo do computador."""
    from hefesto_dualsense4unix.profiles.loader import save_profile

    cru = perfil.model_dump(mode="json", exclude_unset=True)
    if globais:
        _remendar(cru, globais)
    if por_controle:
        controles = dict(cru.get("controllers") or {})
        existentes = _entradas_por_chave(controles)
        for identidade, secoes in por_controle.items():
            original = existentes.get(identidade, identidade)
            entrada = dict(controles.get(original) or {})
            _remendar(entrada, secoes)
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


def onde_grava(cartao: str, perfil: Profile | None) -> str:
    """``"jogo"`` ou ``"computador"``: onde um clique neste cartão grava.

    O que se muda vale para o PERFIL ATIVO (D-0610-O-ESCOPO-SAI-DAS-ABAS): o do
    jogo aberto; sem jogo (nenhum perfil, ou o Freestyle, que não sobrepõe
    nada), o do computador. Não há mais escopo para escolher na tela.
    """
    if cartao not in SECOES:
        raise KeyError(f"{cartao!r} não é um cartão do computador")
    if perfil is None or e_o_freestyle(perfil.name):
        return COMPUTADOR
    return JOGO


def gravar(
    cartao: str,
    campos: Mapping[str, Any],
    *,
    uniq: object = None,
    perfil_ativo: str | None = None,
    origem: str | None = None,
) -> str:
    """O único escritor de um cartão do computador. Devolve onde gravou."""
    perfil = _carregar_cru(perfil_ativo)
    onde = onde_grava(cartao, perfil)
    campos = _com_os_pares(campos)
    if onde == JOGO and perfil is not None:
        _no_perfil(perfil, campos, uniq, origem)
    else:
        _no_computador(campos, uniq)
    logger.info("cartao_gravado", cartao=cartao, onde=onde, perfil=perfil_ativo or "")
    return onde


_IGUAL: Any = object()


def _houve_mudanca(secao: str, mudou: Any) -> bool:
    """``mudou`` (a volta de ``_diferenca_de_secao``) traz algo a gravar?"""
    if mudou is _IGUAL:
        return False
    return mudou is None or secao not in _MODELOS or bool(mudou)


def _diferenca_de_secao(secao: str, antes: Any, depois: Any) -> Any:
    """O que mudou numa seção: ``{campo: valor}``, ``None`` (tirada), ``{}`` ou ``_IGUAL``."""
    if secao not in _MODELOS:
        return depois if antes != depois else _IGUAL
    if depois is None:
        return None if antes is not None else {}
    novo = depois.model_dump(mode="json", exclude_unset=True)
    velho = antes.model_dump(mode="json", exclude_unset=True) if antes is not None else {}
    mudou = {c: v for c, v in novo.items() if velho.get(c, object()) != v}
    mudou.update({c: None for c in velho if c not in novo})
    for par in PARES.get(secao, ()):
        if set(mudou) & set(par):
            for campo in par:
                if campo not in mudou and campo in novo:
                    mudou[campo] = novo[campo]
    return mudou


def o_que_mudou(
    cartao: str, antes: Profile, depois: Profile, uniq: object = None
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """``(globais, {identidade: seções})`` do que mudou de ``antes`` para ``depois``."""
    secao_do_cartao = SECOES[cartao]
    globais: dict[str, Any] = {}
    if uniq is None:
        for secao in secao_do_cartao.globais:
            mudou = _diferenca_de_secao(
                secao, getattr(antes, secao, None), getattr(depois, secao, None))
            if _houve_mudanca(secao, mudou):
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
            if _houve_mudanca(secao, mudou):
                por_controle.setdefault(identidade, {})[secao] = mudou
    return globais, por_controle


def _com_a_lapide_do_que_se_apagou(globais: dict[str, Any], computador: Any) -> dict[str, Any]:
    """As teclas que o jogo APAGOU e o computador define, com a lápide ``[]`` no lugar.

    O perfil do jogo só diz o que difere, e a chave ausente quer dizer «herde».
    Apagar uma tecla que o computador define grava o dicionário SEM ela, e a
    junção (``{**computador, **jogo}``) a devolve: o gesto «apagar» valia só
    quando o computador não tinha aquela tecla. A lápide é o «nada» que já
    existe — a lista vazia, que o schema aceita e a resolução lê como
    «— Nada —» —, e a junção copia a chave presente do jogo, vazia ou não.

    SÓ ``key_bindings``, e a razão é de vocabulário. Dentro de um dicionário de
    teclas, chave ausente já SIGNIFICA «nada» (``acoes.tabela_efetiva``), e todo
    gesto que quer o de fábrica ESCREVE o de fábrica (``padrao_da_tecla`` põe os
    tokens, não tira a chave): apagar é o único jeito de uma chave sumir. Já em
    ``button_actions`` a ausência é «herde», o «nada» é o valor ``__NADA__``
    escolhido na tabela (a junção já o guarda), e a ausência vem do «voltar ao
    padrão» (``padrao_da_tecla`` tira a chave da vista, forma idêntica à de
    «apagar»): lápide ali transformaria o degrau
    D-0110-VOLTAR-AO-PADRAO-E-UM-DEGRAU em «nada».

    A tecla procurada é a do COMPUTADOR, não a da vista: o jogo com
    ``key_bindings == {}`` tem a vista sem o computador, e o dicionário que ele
    grava ao mudar um campo faria a junção voltar a valer; toda tecla do
    computador que fica de fora do que o jogo grava ganha a lápide.

    ``{}`` fica como está: o «tudo ou nada» já ignora o computador por inteiro.
    """
    escritas = globais.get("key_bindings")
    if not isinstance(escritas, Mapping) or not escritas:
        return globais
    do_computador = computador.global_.key_bindings or {}
    apagadas: dict[str, list[str]] = {
        botao: [] for botao, teclas in do_computador.items()
        if botao not in escritas and teclas
    }
    if not apagadas:
        return globais
    return {**globais, "key_bindings": {**escritas, **apagadas}}


def perfil_vazio() -> Profile:
    """Um perfil que não escolhe nada: a base do computador quando não há perfil ativo."""
    return Profile.model_validate({"name": "computador", "match": {"type": "manual"}})


def o_perfil_sem_perfil_ativo(computador: Any = None) -> Profile:
    """O perfil que vale sem perfil ativo: o padrão do computador por baixo do perfil vazio.

    ``computador`` None é o do disco (:func:`o_computador`). A luz, o tato e as abas
    perguntam isto aqui, e não montam o par à mão.
    """
    if computador is None:
        computador = o_computador()
    return perfil_que_vale(perfil_vazio(), computador)


def gravar_pelo_gesto(
    cartao: str,
    nome: str,
    muda: Callable[[Profile], Profile | None],
    *,
    uniq: object = None,
    origem: str | None = None,
) -> tuple[str, Profile | None]:
    """O gesto de um cartão, gravado no perfil ativo (o do jogo, ou o do computador).

    O gesto roda sobre o que VALE (o perfil com o computador por baixo) e só a
    diferença é gravada, onde ``onde_grava`` manda: o jogo não copia o cartão
    inteiro, guarda o campo que mudou.
    """
    from hefesto_dualsense4unix.profiles import loader

    cru = loader.load_profile(nome) if nome else None
    onde = onde_grava(cartao, cru)
    computador = o_computador()
    vista = (perfil_que_vale(cru, computador) if cru is not None
             else o_perfil_sem_perfil_ativo(computador))
    novo = muda(vista)
    if novo is not None:
        globais, por_controle = o_que_mudou(cartao, vista, novo, uniq)
        if onde == JOGO and cru is not None:
            globais = _com_a_lapide_do_que_se_apagou(globais, computador)
            if globais or por_controle:
                _no_perfil_so_o_que_mudou(
                    cru, _com_os_pares(globais),
                    {i: _com_os_pares(sec) for i, sec in por_controle.items()}, origem)
        else:
            if globais:
                _no_computador(_com_os_pares(globais), None)
            for identidade, secoes in por_controle.items():
                _no_computador(_com_os_pares(secoes), identidade)
        logger.info("cartao_gravado", cartao=cartao, onde=onde, perfil=nome)
    return onde, novo


SUFIXO_DA_COPIA = ".antes-do-computador"

_ESCALARES_DO_COMPUTADOR: tuple[str, ...] = (
    "button_actions", "key_bindings", "teclado_emulado",
    "teclado_so_no_jogo", "teclado_sempre", "tabela_no_jogo",
)

_PS_QUE_E_DA_TABELA: frozenset[str] = frozenset({"__NADA__", "__STEAM__"})


def _sem_o_ps_da_tabela(acoes: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if acoes is None:
        return None
    return {b: a for b, a in acoes.items() if not (b == "ps" and a in _PS_QUE_E_DA_TABELA)}


def efetivo(perfil: Profile, computador: Any) -> dict[tuple[str, ...], Any]:
    """O valor que cada campo do :data:`SECOES` TEM para o aparelho. Para comparar."""
    vista = perfil_que_vale(perfil, computador)
    saida: dict[tuple[str, ...], Any] = {}
    for secao in ("leds", "rumble", "speaker", "mic", "mouse"):
        modelo = getattr(vista, secao, None)
        dados = modelo.model_dump(mode="json") if modelo is not None else {}
        for campo, valor in dados.items():
            saida[("global", secao, campo)] = valor
    for secao in _ESCALARES_DO_COMPUTADOR:
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
    for secao in _ESCALARES_DO_COMPUTADOR:
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
    for secao in _ESCALARES_DO_COMPUTADOR:
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
    """O perfil sem o que já vale igual pelo computador. Devolve ``(perfil, saíram)``."""
    if e_o_freestyle(perfil.name):
        cru = perfil.model_dump(mode="json", exclude_unset=True)
        saiu = 0
        for secao in ("leds", "rumble", "speaker", "button_actions", "key_bindings",
                      "teclado_emulado", "teclado_so_no_jogo", "teclado_sempre", "tabela_no_jogo"):
            saiu += secao in cru
            cru.pop(secao, None)
        if isinstance(cru.get("mouse"), dict):
            do_mouse = ("speed", "scroll_speed", "point_and_click")
            saiu += sum(c in cru["mouse"] for c in do_mouse)
            cru["mouse"] = {k: v for k, v in cru["mouse"].items() if k not in do_mouse}
        controles = {}
        for original, entrada in dict(cru.get("controllers") or {}).items():
            resto = {s: v for s, v in dict(entrada).items() if s not in _CAMPOS_DO_CONTROLE}
            for secao in CAMPOS_DO_CONTROLE_NO_COMPUTADOR:
                fica = _sem_a_parte_do_computador(secao, dict(entrada).get(secao))
                if fica is not None:
                    resto[secao] = fica
            saiu += sum(resto.get(s) != v for s, v in dict(entrada).items())
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
    """O documento do computador que nasce do Freestyle (o que ele escreveu)."""
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
            if mouse.point_and_click:
                do_global["mouse"]["point_and_click"] = mouse.point_and_click
        acoes = _sem_o_ps_da_tabela(freestyle.button_actions)
        if acoes:
            do_global["button_actions"] = acoes
        if freestyle.key_bindings is not None:
            do_global["key_bindings"] = freestyle.key_bindings
        if freestyle.teclado_emulado is not None:
            do_global["teclado_emulado"] = freestyle.teclado_emulado
        for escalar in ("teclado_so_no_jogo", "teclado_sempre", "tabela_no_jogo"):
            if getattr(freestyle, escalar) is not None:
                do_global[escalar] = getattr(freestyle, escalar)
        for original, entrada in (freestyle.controllers or {}).items():
            identidade = chave(original)
            if identidade is None:
                continue
            dados_entrada = {
                secao: {c: v for c, v in _so_a_parte_do_computador(
                    secao, valor.model_dump(mode="json", exclude_unset=True)).items()
                        if v is not None}
                for secao in _CAMPOS_DO_CONTROLE
                if (valor := getattr(entrada, secao, None)) is not None
            }
            dados_entrada = {s: v for s, v in dados_entrada.items() if v}
            if dados_entrada:
                controles[identidade] = dados_entrada
    if "mouse" not in do_global:
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


def _o_ps_do_freestyle_vai_ao_sexto(freestyle: Profile | None) -> None:
    """O que o PS sozinho fazia fora do jogo muda de dono sem se perder."""
    if freestyle is None:
        return
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, gravar_maquina

    faz = {"__NADA__": ag.NADA, "__STEAM__": ag.ABRIR_A_STEAM}.get(
        str((freestyle.button_actions or {}).get("ps") or ""))
    if faz is None or ag.GESTO_DO_PS in (carregar_maquina().gestos or {}):
        return
    if gravar_maquina({"gestos": {ag.GESTO_DO_PS: {"faz": faz}}}):
        logger.info("ps_do_freestyle_foi_ao_sexto", faz=faz)


def migrar_uma_vez() -> dict[str, int] | None:
    """O computador nasce do Freestyle, e cada perfil perde o que já vale igual."""
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
    _o_ps_do_freestyle_vai_ao_sexto(freestyle)
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


def _identidades(perfil: Profile, uniq: object) -> list[str]:
    if uniq is not None:
        identidade = chave(uniq)
        return [identidade] if identidade else []
    return sorted(_entradas_por_chave(perfil.controllers))


def voltar_ao_do_computador(cartao: str, uniq: object, perfil: str) -> Profile:
    """Tira do perfil o que ele escolheu neste cartão: volta a valer o computador."""
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
            for nome in secao.por_controle:
                fica = _sem_a_parte_do_computador(nome, dict(controles[original]).get(nome))
                if fica is not None:
                    entrada[nome] = fica
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


__all__ = [
    "COMPUTADOR",
    "DO_JOGO",
    "JA_DO_COMPUTADOR",
    "JOGO",
    "PARES",
    "SECOES",
    "SUFIXO_DA_COPIA",
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
    "migrar_uma_vez",
    "o_computador",
    "o_perfil_sem_perfil_ativo",
    "o_que_mudou",
    "o_que_vale",
    "onde_grava",
    "perfil_que_vale",
    "perfil_vazio",
    "restaurar_o_computador",
    "selo_da_maquina",
    "semente_do_freestyle",
    "sobrepoe",
    "velocidades_do_computador",
    "voltar_ao_do_computador",
    "voltar_o_computador_ao_de_fabrica",
]
