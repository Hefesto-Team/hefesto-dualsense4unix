"""A camada de cada gesto, e a marca que diz de quem é o valor. Das dez abas."""
from __future__ import annotations

import json
from typing import Any

from hefesto_dualsense4unix.interface import marca_da_camada as _marca

from . import Contexto, gesto
from . import perfil as _perfil

COMPUTADOR, CONTROLE, JOGO, ATO, JANELA = (
    "computador", "controle", "jogo", "ato", "janela")
CAMADAS = frozenset({COMPUTADOR, CONTROLE, JOGO, ATO, JANELA})

_J, _C, _T, _A, _W = JOGO, COMPUTADOR, CONTROLE, ATO, JANELA

CAMADA: dict[tuple[str, str], str] = {
    ("01-jogar.html", "cadeado"): _C,
    ("01-jogar.html", "escolher-na-fita"): _W,
    ("01-jogar.html", "hefesto"): _J,
    ("01-jogar.html", "mascara"): _J,
    ("01-jogar.html", "modo-dualsense"): _J,
    ("01-jogar.html", "modo-navegacao"): _J,
    ("01-jogar.html", "modo-steam"): _J,
    ("01-jogar.html", "modo-xbox"): _J,
    ("01-jogar.html", "reconectar"): _A,
    ("02-controles.html", "escolher-na-fita"): _W,
    ("02-controles.html", "ganho-mic"): _C,
    ("02-controles.html", "inclinacao"): _J,
    ("02-controles.html", "mic-retorno"): _W,
    ("02-controles.html", "mira"): _J,
    ("02-controles.html", "mudo"): _C,
    ("02-controles.html", "rota"): _C,
    ("02-controles.html", "sensor"): _C,
    ("02-controles.html", "toque"): _J,
    ("02-controles.html", "volume"): _C,
    ("03-gatilhos.html", "em-todos"): _J,
    ("03-gatilhos.html", "guardar"): _J,
    ("03-gatilhos.html", "modo"): _J,
    ("03-gatilhos.html", "pronto"): _J,
    ("04-iluminacao.html", "apagar"): _C,
    ("04-iluminacao.html", "auto-cores"): _C,
    ("04-iluminacao.html", "brilho"): _C,
    ("04-iluminacao.html", "brilho-luzes"): _C,
    ("04-iluminacao.html", "cor"): _C,
    ("04-iluminacao.html", "player"): _T,
    ("04-iluminacao.html", "reenviar"): _C,
    ("05-vibracao.html", "forca"): _C,
    ("05-vibracao.html", "haptica"): _C,
    ("05-vibracao.html", "intensidade"): _C,
    ("05-vibracao.html", "lado"): _C,
    ("05-vibracao.html", "motor"): _C,
    ("05-vibracao.html", "parar"): _A,
    ("05-vibracao.html", "testar"): _A,
    ("05-vibracao.html", "testar-haptica"): _A,
    ("06-navegacao.html", "acao-do-gesto"): _C,
    ("06-navegacao.html", "fechar-definicoes"): _W,
    ("06-navegacao.html", "fechar-ponto"): _W,
    ("06-navegacao.html", "fechar-teclas"): _W,
    ("06-navegacao.html", "fechar-troca"): _W,
    ("06-navegacao.html", "guardar-definicoes"): _C,
    ("06-navegacao.html", "guardar-ponto"): _J,
    ("06-navegacao.html", "guardar-remapeamento"): _J,
    ("06-navegacao.html", "guardar-teclas"): _C,
    ("06-navegacao.html", "linha-de-botao"): _W,
    ("06-navegacao.html", "linha-de-troca"): _W,
    ("06-navegacao.html", "modo"): _J,
    ("06-navegacao.html", "modo-steam"): _C,
    ("06-navegacao.html", "navegacao-interna"): _C,
    ("06-navegacao.html", "padrao-da-aba"): _C,
    ("06-navegacao.html", "padrao-da-tecla"): _C,
    ("06-navegacao.html", "padrao-definicoes"): _C,
    ("06-navegacao.html", "padrao-remapeamento"): _J,
    ("06-navegacao.html", "tecla-escrita"): _W,
    ("06-navegacao.html", "teclado"): _C,
    ("06-navegacao.html", "vel-cursor"): _C,
    ("06-navegacao.html", "vel-rolagem"): _C,
    ("07-lancadores.html", "abrir-lancador"): _A,
    ("07-lancadores.html", "adicionar-lancador"): _C,
    ("07-lancadores.html", "criar-perfil-para-um-jogo"): _J,
    ("07-lancadores.html", "detectar"): _A,
    ("07-lancadores.html", "procurar"): _A,
    ("07-lancadores.html", "procurar-o-arquivo"): _C,
    ("08-conexoes.html", "abrir-adaptador"): _W,
    ("08-conexoes.html", "aceitar-sugestao"): _A,
    ("08-conexoes.html", "adaptador-historico"): _W,
    ("08-conexoes.html", "adaptador-renomear"): _C,
    ("08-conexoes.html", "adaptador-reordenar"): _C,
    ("08-conexoes.html", "alvo"): _W,
    ("08-conexoes.html", "aparelho-menu"): _W,
    ("08-conexoes.html", "aparelho-renomear"): _T,
    ("08-conexoes.html", "cancelar-mudanca"): _W,
    ("08-conexoes.html", "conectar-aparelho"): _A,
    ("08-conexoes.html", "confirmar-esquecer"): _A,
    ("08-conexoes.html", "confirmar-mudanca"): _A,
    ("08-conexoes.html", "custo-luz"): _T,
    ("08-conexoes.html", "custo-mic"): _T,
    ("08-conexoes.html", "custo-som"): _T,
    ("08-conexoes.html", "custo-vibracao"): _T,
    ("08-conexoes.html", "dispensar-linha"): _A,
    ("08-conexoes.html", "dono-renomear"): _T,
    ("08-conexoes.html", "entrada-comecar"): _C,
    ("08-conexoes.html", "entrada-face"): _C,
    ("08-conexoes.html", "entrada-levantar"): _C,
    ("08-conexoes.html", "entrada-nao-alcanco"): _C,
    ("08-conexoes.html", "entrada-parar"): _C,
    ("08-conexoes.html", "entrada-pular"): _C,
    ("08-conexoes.html", "equilibrar-radio"): _A,
    ("08-conexoes.html", "escolher-adaptador"): _W,
    ("08-conexoes.html", "escolher-aparelho"): _W,
    ("08-conexoes.html", "escolher-entrada"): _C,
    ("08-conexoes.html", "escolher-na-fita"): _W,
    ("08-conexoes.html", "esquecer-aparelho"): _A,
    ("08-conexoes.html", "examinar-portas"): _C,
    ("08-conexoes.html", "ignorar"): _C,
    ("08-conexoes.html", "ligar-mesmo-assim"): _A,
    ("08-conexoes.html", "luz-nao-acende"): _C,
    ("08-conexoes.html", "mapear-comecar"): _C,
    ("08-conexoes.html", "mapear-gravar"): _C,
    ("08-conexoes.html", "mapear-parar"): _C,
    ("08-conexoes.html", "nova-entrada"): _C,
    ("08-conexoes.html", "nova-extensao"): _C,
    ("08-conexoes.html", "nova-face"): _C,
    ("08-conexoes.html", "novo-hub"): _C,
    ("08-conexoes.html", "parear-aparelho"): _A,
    ("08-conexoes.html", "parear-de-novo"): _A,
    ("08-conexoes.html", "perfil-do-controle"): _T,
    ("08-conexoes.html", "radio-procurar"): _A,
    ("08-conexoes.html", "receptor-descobrir"): _A,
    ("08-conexoes.html", "sala-altura"): _C,
    ("08-conexoes.html", "sala-visada"): _C,
    ("08-conexoes.html", "sugerir-alocacao"): _A,
    ("08-conexoes.html", "tentar-de-novo"): _A,
    ("08-conexoes.html", "tirar-daqui"): _C,
    ("08-conexoes.html", "trazer-para-ca"): _A,
    ("08-conexoes.html", "vizinho-o-que-e"): _C,
    ("09-sistema.html", "aplicar-aos-jogos"): _C,
    ("09-sistema.html", "atualizar"): _A,
    ("09-sistema.html", "autostart"): _C,
    ("09-sistema.html", "copiar-registro"): _A,
    ("09-sistema.html", "corrigir-modo"): _A,
    ("09-sistema.html", "corrigir-vulkan"): _C,
    ("09-sistema.html", "fixar-proton"): _C,
    ("09-sistema.html", "parar-ou-retomar"): _A,
    ("09-sistema.html", "perfil-da-mesa"): _C,
    ("09-sistema.html", "refazer-consertos"): _C,
    ("09-sistema.html", "reiniciar"): _A,
    ("09-sistema.html", "restaurar-de-fabrica"): _C,
    ("10-perfis.html", "ativar"): _J,
    ("10-perfis.html", "detectar"): _A,
    ("10-perfis.html", "duplicar"): _J,
    ("10-perfis.html", "editor.ambiente"): _J,
    ("10-perfis.html", "editor.estilo"): _J,
    ("10-perfis.html", "editor.jogo"): _J,
    ("10-perfis.html", "editor.nome"): _J,
    ("10-perfis.html", "editor.prioridade"): _J,
    ("10-perfis.html", "largura-da-coluna"): _W,
    ("10-perfis.html", "novo"): _J,
    ("10-perfis.html", "ordenar"): _W,
    ("10-perfis.html", "recarregar"): _A,
    ("10-perfis.html", "remover"): _J,
    ("10-perfis.html", "selecionar"): _W,
    ("*", _marca.SO_NESTE_JOGO): _J,
    ("*", _marca.VOLTAR_AO_DO_COMPUTADOR): _J,
}


_PERFIL_LIDO: dict[str, tuple[str, Any]] = {}


def _perfil_do_jogo(nome: str) -> Any:
    """O ``Profile`` cru do ativo quando ele é um jogo; ``None`` com o Freestyle ou sem."""
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
    from hefesto_dualsense4unix.profiles.schema import Profile

    if not nome or opc.e_o_freestyle(nome):
        return None
    cru = _perfil.ativo(nome)
    if not cru:
        return None
    selo = json.dumps(cru, sort_keys=True, default=str)
    lido = _PERFIL_LIDO.get(nome)
    if lido is not None and lido[0] == selo:
        return lido[1]
    try:
        prof = Profile.model_validate(cru)
    except Exception:
        prof = None
    _PERFIL_LIDO[nome] = (selo, prof)
    return prof


def cartoes_da_pagina(pagina: str) -> list[str]:
    """Os cartões do computador que aquela página mostra."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import SECOES

    return [c for c, s in SECOES.items() if s.pagina == pagina]


_FORCAS_DE_UM_CONTROLE = frozenset({"economia", "balanceado", "max", "custom"})


def vivos(ctx: Contexto, cartao: str, uniq: str | None) -> dict[str, Any]:
    """O que o aparelho tem AGORA no cartão, na forma da seção do perfil."""
    state = ctx.state or {}
    if cartao == "som" and uniq:
        from .a02_controles import _bloco_do_speaker

        bloco = _bloco_do_speaker(ctx.por_uniq(uniq)) or {}
        volume = bloco.get("volume")
        if isinstance(volume, int) and not isinstance(volume, bool):
            return {"speaker": {"volume": volume, "muted": bool(bloco.get("muted"))}}
        return {}
    if cartao == "vibracao":
        forca = str(state.get("rumble_policy") or "")
        mult = state.get("rumble_mult_applied")
        if forca in _FORCAS_DE_UM_CONTROLE - {"custom"}:
            return {"rumble": {"policy": forca}}
        if forca == "custom" and isinstance(mult, (int, float)) and not isinstance(mult, bool):
            return {"rumble": {"policy": forca, "custom_mult": float(mult)}}
        return {}
    if cartao == "mouse":
        rato = state.get("mouse_emulation")
        if isinstance(rato, dict) and all(
                isinstance(rato.get(c), int) and not isinstance(rato.get(c), bool)
                for c in ("speed", "scroll_speed")):
            return {"mouse": {"enabled": bool(rato.get("enabled")),
                              "speed": rato["speed"], "scroll_speed": rato["scroll_speed"]}}
        return {}
    if cartao == "teclado":
        teclado = state.get("keyboard_emulation")
        if isinstance(teclado, dict) and isinstance(teclado.get("enabled"), bool):
            return {"teclado_emulado": teclado["enabled"]}
        return {}
    return {}


def marcas(pagina: str, ctx: Contexto) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """``(da mesa, {uniq: do controle})``: o miolo de cada marca da página."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
        SECOES,
        o_computador,
        pode_so_neste_jogo,
        sobrepoe,
    )

    cartoes = cartoes_da_pagina(pagina)
    if not cartoes:
        return {}, {}
    nome = _perfil.nome_do_ativo(ctx.state).strip()
    prof = _perfil_do_jogo(nome)
    jogo = prof.name if prof is not None else ""
    computador = o_computador() if prof is not None else None

    def _miolo(cartao: str, uniq: str | None) -> str:
        sobre = prof is not None and sobrepoe(prof, cartao, uniq)
        dono = jogo if sobre or pode_so_neste_jogo(
            cartao, uniq, prof, computador, vivos(ctx, cartao, uniq)) else ""
        return _marca.miolo(cartao, jogo=dono, sobrepoe=sobre)

    da_mesa: dict[str, str] = {}
    por_controle: dict[str, dict[str, str]] = {}
    for cartao in cartoes:
        if SECOES[cartao].por_controle:
            for c in ctx.conectados or []:
                uniq = str(c.get("uniq") or "")
                if not uniq:
                    continue
                por_controle.setdefault(uniq, {})[_marca.campo(cartao)] = _miolo(cartao, uniq)
        else:
            da_mesa[_marca.campo(cartao)] = _miolo(cartao, None)
    return da_mesa, por_controle


def com_a_camada(pagina: str, ctx: Contexto, fora: dict[str, Any]) -> dict[str, Any]:
    """O pacote da aba com as marcas que a página carregada tem onde pousar."""
    from . import POR_CONTROLE, alvos_da_pagina

    da_mesa, por_controle = marcas(pagina, ctx)
    if not da_mesa and not por_controle:
        return fora
    lugares = set(alvos_da_pagina(pagina))
    da_mesa = {k: v for k, v in da_mesa.items() if k in lugares}
    por_controle = {u: {k: v for k, v in d.items() if k in lugares}
                    for u, d in por_controle.items()}
    por_controle = {u: d for u, d in por_controle.items() if d}
    if not da_mesa and not por_controle:
        return fora
    saida = dict(fora)
    if da_mesa:
        saida["mesa"] = {**dict(saida.get("mesa") or {}), **da_mesa}
    if por_controle:
        nome = next((n for n in POR_CONTROLE if n in saida), POR_CONTROLE[0])
        colunas = {k: dict(v) for k, v in dict(saida.get(nome) or {}).items()}
        for uniq, campos in por_controle.items():
            colunas.setdefault(uniq, {}).update(campos)
        saida[nome] = colunas
    return saida


def _o_cartao_e_o_jogo(ctx: Contexto, o: dict[str, Any]) -> tuple[str, Any, str]:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import SECOES

    cartao = str(o.get("linha") or "")
    if cartao not in SECOES:
        raise ValueError(f"a marca não disse qual cartão (veio {cartao!r})")
    nome = _perfil.nome_do_ativo(ctx.state).strip()
    if _perfil_do_jogo(nome) is None:
        raise RuntimeError("não há jogo ativo: o que está aqui é do computador.")
    uniq = str(o.get("uniq") or "") if SECOES[cartao].por_controle else ""
    return cartao, uniq or None, nome


@gesto("*", _marca.SO_NESTE_JOGO, grava="so_neste_jogo")
def so_neste_jogo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Só neste jogo»: o jogo ativo passa a guardar este cartão (com o que vale agora)."""
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    cartao, uniq, nome = _o_cartao_e_o_jogo(ctx, o)
    _perfil._com_o_src()
    opc.so_neste_jogo(cartao, uniq, nome, vivos(ctx, cartao, uniq))
    _perfil.reaplicar(nome, ctx, p)


@gesto("*", _marca.VOLTAR_AO_DO_COMPUTADOR, grava="voltar_ao_do_computador")
def voltar_ao_do_computador(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Voltar ao do PC»: o jogo esquece este cartão, e vale o computador."""
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    cartao, uniq, nome = _o_cartao_e_o_jogo(ctx, o)
    _perfil._com_o_src()
    opc.voltar_ao_do_computador(cartao, uniq, nome)
    _perfil.reaplicar(nome, ctx, p)


__all__ = [
    "ATO",
    "CAMADA",
    "CAMADAS",
    "COMPUTADOR",
    "CONTROLE",
    "JANELA",
    "JOGO",
    "cartoes_da_pagina",
    "com_a_camada",
    "marcas",
    "so_neste_jogo",
    "vivos",
    "voltar_ao_do_computador",
]
