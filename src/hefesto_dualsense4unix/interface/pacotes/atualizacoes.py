"""Os gestos da pergunta da atualização e do andamento, válidos em toda aba.

A caixa (:mod:`interface.atualizacoes`) nasce por cima da aba aberta: o andamento enquanto a fila
roda ou até quem usa fechar o fim, a pergunta quando o prazo vence com peça nova, e as versões
anteriores quando pedidas. O que se escolhe aqui é o ``atualizador.json`` do motor, e a fila roda
fora da janela (:func:`atualizador.soltar`).
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.interface import atualizacoes as tela

from . import Contexto, fios, gesto

PAGINA = "*"
INTERVALO_DA_LEITURA_S = 0.5
VALIDADE_DO_FIM_S = 3600.0
PRAZO_PARA_TENTAR_S = 3600.0
PASSO_PARA_TENTAR_S = 2.0
IDADE_DA_CONFERENCIA_S = 600.0

FORCAR = "\0"

TELA: dict[str, Any] = {"vista": "", "perguntou": False, "escondida": 0.0, "lido_em": 0.0,
                        "enviado": "", "aba": "", "vez": 0, "calculado": None,
                        "calculando": False}


def _com_a_escolha(conferencia: dict[str, Any], escolha: at.Escolha) -> dict[str, Any]:
    pecas = []
    for item in conferencia.get("pecas") or []:
        if isinstance(item, dict):
            marcada = escolha.marcadas.get(str(item.get("id")), bool(item.get("marcada", True)))
            pecas.append({**item, "marcada": marcada and item.get("volta", 1) == 1})
    return {**conferencia, "pecas": pecas}


def conferencia_vista() -> dict[str, Any]:
    return _com_a_escolha(at.ler_a_conferencia(), at.ler_a_escolha())


def _jogo_aberto(ctx: Contexto | None) -> bool:
    from hefesto_dualsense4unix.app.actions.home_actions import jogo_com_autoridade

    return jogo_com_autoridade(getattr(ctx, "state", None))


def _nome_do_jogo(ctx: Contexto | None) -> str:
    """O nome do jogo aberto: o da Steam pelo appid, e senão o do perfil de jogo que entrou."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import nome_do_appid
    from hefesto_dualsense4unix.profiles.loader import perfil_em_disco
    from hefesto_dualsense4unix.profiles.schema import perfil_e_de_jogo

    estado = getattr(ctx, "state", None)
    if not isinstance(estado, dict):
        return ""
    jogo = estado.get("jogo_steam")
    appid = jogo.get("appid") if isinstance(jogo, dict) else None
    if isinstance(appid, int) and not isinstance(appid, bool):
        nome = nome_do_appid(str(appid))
        if nome:
            return nome
    ativo = estado.get("active_profile")
    if not isinstance(ativo, str) or not ativo.strip():
        return ""
    perfil = perfil_em_disco(ativo)
    if perfil is None or not perfil_e_de_jogo(perfil):
        return ""
    return str(getattr(perfil, "nome_do_jogo", None) or perfil.name).strip()


def _inicio(andamento: dict[str, Any]) -> float:
    try:
        return float(andamento.get("inicio", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _andamento_a_mostrar(andamento: dict[str, Any], rodando: bool, agora: float) -> bool:
    """Arquivo ausente, meio escrito ou de outra forma é «sem andamento», nunca erro."""
    pecas = andamento.get("pecas")
    if not isinstance(pecas, list) or not any(isinstance(p, dict) for p in pecas):
        return False
    inicio = _inicio(andamento)
    if not inicio or inicio == TELA["escondida"]:
        return False
    if rodando:
        return True
    return not andamento.get("visto") and agora - inicio < VALIDADE_DO_FIM_S


def conteudo(ctx: Contexto | None, *, agora: float | None = None) -> str:
    """O HTML da caixa agora, ou vazio: a caixa fechada."""
    momento = time.time() if agora is None else agora
    andamento = at.ler_o_andamento()
    rodando = at.em_curso()
    if _andamento_a_mostrar(andamento, rodando, momento):
        TELA["vista"] = "andamento"
        return tela.html_do_andamento(andamento, rodando=rodando)
    if TELA["vista"] == "andamento":
        TELA["vista"] = ""
    if not TELA["vista"] and not TELA["perguntou"] and at.hora_da_pergunta(momento):
        TELA["perguntou"] = True
        TELA["vista"] = "pergunta"
    if TELA["vista"] == "pergunta":
        escolha = at.ler_a_escolha()
        aberto = _jogo_aberto(ctx)
        return tela.html_da_pergunta(conferencia_vista(), {"sozinho": escolha.sozinho,
                                                          "dias": escolha.dias},
                                     jogo_aberto=aberto,
                                     nome_do_jogo=_nome_do_jogo(ctx) if aberto else "")
    if TELA["vista"] == "voltar":
        voltam = [p.id for p in at.pecas() if p.voltar is not None]
        return tela.html_das_anteriores(at.ler_as_anteriores(), voltam)
    return ""


def _calcular(ctx: Contexto | None, vez: int) -> None:
    try:
        TELA["calculado"] = (vez, conteudo(ctx))
    except (OSError, ValueError) as erro:
        print(f"[atualizações] a caixa não se leu: {erro}", file=sys.stderr)
    finally:
        TELA["calculando"] = False


def pintar(ponte: Any, pagina: str, ctx: Contexto | None, *, em_fundo: bool = True) -> None:
    """Repinta a caixa só quando o conteúdo ou a aba muda; o motor se lê fora do fio da janela.

    A cada tique: o conteúdo pronto da leitura anterior vai à página, se mudou, e uma leitura
    nova parte no máximo duas vezes por segundo. A aba nova nasce sem a caixa.
    """
    if pagina != TELA["aba"]:
        TELA["aba"], TELA["enviado"] = pagina, ""
        TELA["lido_em"] = 0.0
    pronto = TELA["calculado"]
    if pronto is not None:
        TELA["calculado"] = None
        vez, novo = pronto
        if vez == TELA["vez"] and novo != TELA["enviado"]:
            TELA["enviado"] = novo
            ponte.rodar(tela.js_da_caixa(novo))
    agora = time.monotonic()
    if TELA["calculando"] or agora - TELA["lido_em"] < INTERVALO_DA_LEITURA_S:
        return
    TELA["lido_em"], TELA["calculando"] = agora, True
    if em_fundo:
        fios.soltar("atualizador-caixa", _calcular, ctx, TELA["vez"])
    else:
        _calcular(ctx, TELA["vez"])


def _repintar() -> None:
    TELA["vez"] += 1
    TELA["lido_em"] = 0.0
    TELA["calculado"] = None
    TELA["calculando"] = False
    TELA["enviado"] = FORCAR


def _conferir_em_fundo() -> None:
    conferencia = at.ler_a_conferencia()
    if time.time() - float(conferencia.get("em", 0) or 0) < IDADE_DA_CONFERENCIA_S:
        return

    def _conferir() -> None:
        try:
            at.conferir(rede=True)
        except OSError as erro:
            print(f"[atualizações] a conferência não gravou: {erro}", file=sys.stderr)
        _repintar()

    fios.soltar("atualizador-conferir", _conferir)


@gesto("*", "atualizacoes-abrir")
def abrir(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O botão «Atualizações» da aba Sistema: o mapa, com a conferência refeita se velha."""
    TELA["vista"] = "pergunta"
    TELA["escondida"] = 0.0
    _conferir_em_fundo()
    _repintar()


@gesto("*", "atualizacoes-anteriores")
def anteriores(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Versões anteriores»: a lista do que volta."""
    TELA["vista"] = "voltar"
    _repintar()


@gesto("*", "atualizacoes-lista")
def lista(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«← Atualizações»: de volta ao mapa."""
    TELA["vista"] = "pergunta"
    _repintar()


@gesto("*", "atualizacoes-fechar")
def fechar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O fechar: esconde o andamento (a fila segue) ou fecha a pergunta; o fim visto não volta."""
    if TELA["vista"] == "andamento":
        andamento = at.ler_o_andamento()
        TELA["escondida"] = _inicio(andamento)
        if not at.em_curso():
            at.marcar_o_andamento_visto()
    TELA["vista"] = ""
    _repintar()


@gesto("*", "atualizacoes-agora-nao", grava="mudar_a_escolha")
def agora_nao(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Agora não»: a pergunta volta no próximo prazo."""
    at.mudar_a_escolha(perguntada_em=time.time())
    TELA["vista"] = ""
    _repintar()


@gesto("*", "atualizacoes-atualizar", grava="instala as peças marcadas e reinicia o serviço")
def atualizar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Atualizar N»: solta a fila das marcadas; com jogo aberto, a fila espera o jogo fechar."""
    ids = tela.ids_para_atualizar(conferencia_vista())
    if not ids:
        raise ValueError("atualizar: nenhuma peça marcada com versão nova")
    if not at.soltar(ids):
        raise RuntimeError("atualizar: a fila não abriu (outra já roda)")
    at.mudar_a_escolha(perguntada_em=time.time())
    TELA["vista"] = ""
    TELA["escondida"] = 0.0
    _repintar()


@gesto("*", "atualizar-sozinho", grava="mudar_a_escolha")
def sozinho(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Atualização automática»: liga ou desliga, e a escolha fica guardada."""
    at.mudar_a_escolha(sozinho=not at.ler_a_escolha().sozinho)
    _repintar()


@gesto("*", "prazo-da-atualizacao", grava="mudar_a_escolha")
def prazo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O menos e o mais do prazo: um dia por clique, entre 1 e 90."""
    try:
        passo = int(str(o.get("v") or "0"))
    except ValueError:
        raise ValueError(f"prazo: passo inválido {o.get('v')!r}") from None
    at.mudar_a_escolha(dias=at.ler_a_escolha().dias + passo)
    _repintar()


def _so_na_troca(o: dict[str, Any]) -> bool:
    return str(o.get("evento") or "change") == "change"


@gesto("*", "peca-da-atualizacao", grava="mudar_a_escolha")
def peca(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A marca de uma peça: entra ou fica de fora, na pergunta e na «Atualização automática»."""
    if not _so_na_troca(o):
        return
    ident = str(o.get("v") or "")
    registro = {x.id: x for x in at.pecas()}
    if ident not in registro or registro[ident].volta != 1:
        raise ValueError(f"peça desconhecida: {ident!r}")
    at.mudar_a_escolha(peca=ident, marcada=not at.ler_a_escolha().marcada(registro[ident]))
    _repintar()


@gesto("*", "pecas-do-grupo", grava="mudar_a_escolha")
def grupo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A marca do grupo: todas as peças de fora com versão nova entram, ou todas saem."""
    if not _so_na_troca(o):
        return
    marcar = str(o.get("v") or "1") == "1"
    for item in conferencia_vista().get("pecas") or []:
        if item.get("grupo") != "hefesto" and item.get("estado") == at.NOVA:
            at.mudar_a_escolha(peca=str(item["id"]), marcada=marcar)
    _repintar()


@gesto("*", "voltar-a-anterior", grava="volta a peça à versão anterior")
def voltar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Voltar a X»: a peça volta e a versão que saiu fica segurada."""
    motivo = at.voltar(str(o.get("v") or ""))
    _repintar()
    if motivo:
        raise RuntimeError(f"voltar: {motivo}")


@gesto("*", "atualizacoes-parar")
def parar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Parar»: a fila sai entre duas etapas."""
    at.pedir_para_parar()
    _repintar()


@gesto("*", "atualizacoes-tentar", grava="instala de novo as peças que falharam")
def tentar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Tentar de novo»: as que falharam voltam à fila quando a de agora terminar."""
    ids = [str(x.get("id")) for x in at.ler_o_andamento().get("pecas") or []
           if isinstance(x, dict) and x.get("selo") == at.FALHOU]
    if not ids:
        raise ValueError("tentar: nenhuma peça falhou")

    def _quando_livre() -> None:
        inicio = time.monotonic()
        while at.em_curso() and time.monotonic() - inicio < PRAZO_PARA_TENTAR_S:
            time.sleep(PASSO_PARA_TENTAR_S)
        at.soltar(ids)
        _repintar()

    TELA["escondida"] = 0.0
    fios.soltar("atualizador-tentar", _quando_livre)


@gesto("*", "atualizacoes-registro")
def registro(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Registro»: o arquivo desta atualização no editor do sistema."""
    from hefesto_dualsense4unix.integrations import fora_do_servico

    caminho = at.caminho_do_registro()
    if not caminho.exists():
        raise ValueError("registro: nada registrado ainda")
    fora_do_servico.abrir(["xdg-open", str(caminho)], env=dict(os.environ),
                          aplicativo="atualizador-registro")


PISO_DA_ABA = 15
PONTE: set[str] = set()
METODOS: set[str] = set()
