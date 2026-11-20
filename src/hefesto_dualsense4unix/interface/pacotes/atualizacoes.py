"""Os gestos da pergunta da atualização e do andamento, válidos em toda aba.

A caixa (:mod:`interface.atualizacoes`) nasce por cima da aba aberta: o andamento enquanto a fila
roda ou até quem usa fechar o fim, a pergunta quando o prazo vence com peça nova, e as versões
anteriores quando pedidas. O que se escolhe aqui é o ``atualizador.json`` do motor, e a fila roda
fora da janela (:func:`atualizador.soltar`).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.integrations import curas_da_casa
from hefesto_dualsense4unix.interface import atualizacoes as tela

from . import Contexto, fios, gesto

PAGINA = "*"
INTERVALO_DA_LEITURA_S = 0.5
VALIDADE_DO_FIM_S = 3600.0
IDADE_DA_CONFERENCIA_S = 600.0

FORCAR = "\0"

TELA: dict[str, Any] = {"vista": "", "perguntou": False, "escondida": 0.0, "lido_em": 0.0,
                        "enviado": "", "aba": "", "vez": 0, "calculado": None,
                        "calculando": False}


def _com_a_escolha(conferencia: dict[str, Any], escolha: at.Escolha,
                   reinstalar: set[str] | frozenset[str] = frozenset(),
                   agora: float | None = None) -> dict[str, Any]:
    """A conferência com a marca de cada peça, a idade em dias da versão de fora e, com a
    «Atualização automática», quando a versão sai da quarentena (``sobe_em``, 0 se já saiu)."""
    momento = time.time() if agora is None else agora
    pecas = []
    for item in conferencia.get("pecas") or []:
        if isinstance(item, dict):
            marcada = escolha.marcadas.get(str(item.get("id")), bool(item.get("marcada", True)))
            try:
                publicada = float(item.get("publicada_em") or 0)
            except (TypeError, ValueError):
                publicada = 0.0
            sobe = at.sobe_sozinha_em(publicada, escolha) if escolha.sozinho else 0.0
            idade = {"idade_dias": max(0, int((momento - publicada) // at.DIA_S)),
                     "sobe_em": sobe if sobe > momento else 0.0} if publicada > 0 else {}
            pecas.append({**item, "marcada": marcada and item.get("volta", 1) == 1,
                          "reinstalar": str(item.get("id")) in reinstalar, **idade})
    return {**conferencia, "pecas": pecas}


def _reinstalar() -> set[str]:
    """As peças em dia marcadas para reinstalar: valem até o «Atualizar», sem ir ao disco."""
    marcadas: set[str] = TELA.setdefault("reinstalar", set())
    return marcadas


def conferencia_vista() -> dict[str, Any]:
    return _com_a_escolha(at.ler_a_conferencia(), at.ler_a_escolha(), _reinstalar())


def _jogo_aberto(ctx: Contexto | None) -> bool:
    from hefesto_dualsense4unix.app.actions.home_actions import jogo_com_autoridade

    return jogo_com_autoridade(getattr(ctx, "state", None))


def _a_steam_segura(andamento: dict[str, Any], ctx: Contexto | None) -> bool:
    """A espera que fechar a Steam solta: a Steam que a fila não fechou, ou um jogo da Steam."""
    from hefesto_dualsense4unix.integrations.proton_pin import _PORQUE_A_STEAM_BARRA

    espera = andamento.get("espera") if andamento.get("fase") == at.ESPERA else None
    if isinstance(espera, dict) and espera.get("motivo") in _PORQUE_A_STEAM_BARRA.values():
        return True
    estado = getattr(ctx, "state", None)
    jogo = estado.get("jogo_steam") if isinstance(estado, dict) else None
    appid = jogo.get("appid") if isinstance(jogo, dict) else None
    return isinstance(appid, int) and not isinstance(appid, bool)


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
    try:
        fim = float(andamento.get("fim_em") or inicio)
    except (TypeError, ValueError):
        fim = inicio
    return not andamento.get("visto") and agora - fim < VALIDADE_DO_FIM_S


def _o_reinicio(andamento: dict[str, Any], rodando: bool) -> str:
    """O porquê de o computador pedir o reinício no fim da fila; vazio com a fila viva."""
    return "" if rodando else curas_da_casa.pede_reinicio(
        trocou_em=at.trocou_o_que_pede_reinicio(andamento))


def _a_pergunta_do_reinicio_aberta() -> bool:
    """A pergunta do reinício está na tela agora, sobre um fim que ainda pede o reinício."""
    if TELA["vista"] != "reiniciar":
        return False
    andamento = at.ler_o_andamento()
    rodando = at.em_curso()
    return _andamento_a_mostrar(andamento, rodando, time.time()) and tela.oferece_o_reinicio(
        andamento, rodando=rodando, pede_reinicio=_o_reinicio(andamento, rodando))


def conteudo(ctx: Contexto | None, *, agora: float | None = None) -> str:
    """O HTML da caixa agora, ou vazio: a caixa fechada."""
    momento = time.time() if agora is None else agora
    andamento = at.ler_o_andamento()
    rodando = at.em_curso()
    espera = rodando and andamento.get("fase") in (at.ESPERA, at.ESPERA_O_JOGO)
    if TELA["vista"] == "registro":
        return tela.html_do_registro(_o_registro())
    if _andamento_a_mostrar(andamento, rodando, momento) \
            and not (espera and TELA["vista"] in ("pergunta", "voltar")):
        reinicio = _o_reinicio(andamento, rodando)
        if TELA["vista"] == "reiniciar" and tela.oferece_o_reinicio(
                andamento, rodando=rodando, pede_reinicio=reinicio):
            return tela.html_da_pergunta_do_reinicio()
        TELA["vista"] = "andamento"
        return tela.html_do_andamento(andamento, rodando=rodando,
                                      parando=rodando and at.parada_pedida(),
                                      pede_reinicio=reinicio,
                                      fecha_a_steam=espera and _a_steam_segura(andamento, ctx))
    if TELA["vista"] in ("andamento", "reiniciar"):
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
                                     nome_do_jogo=_nome_do_jogo(ctx) if aberto else "",
                                     fila_espera=espera)
    if TELA["vista"] == "voltar":
        voltam = [p.id for p in at.pecas() if p.voltar is not None]
        return tela.html_das_anteriores(at.anteriores_a_mostrar(), voltam)
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
    if TELA["vista"] in ("andamento", "registro", "reiniciar"):
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
        raise ValueError("atualizar: nenhuma peça marcada")
    if not at.soltar(ids):
        raise RuntimeError("atualizar: a fila não abriu (outra já roda)")
    _reinstalar().clear()
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
    """A marca de uma peça: a com versão nova entra ou sai, e a escolha fica guardada; a em dia
    entra ou sai da reinstalação, que vale até o «Atualizar»."""
    if not _so_na_troca(o):
        return
    ident = str(o.get("v") or "")
    registro = {x.id: x for x in at.pecas()}
    if ident not in registro or registro[ident].volta != 1:
        raise ValueError(f"peça desconhecida: {ident!r}")
    item = next((i for i in conferencia_vista().get("pecas") or [] if str(i.get("id")) == ident),
                None)
    if item is None or not tela.marcavel(item):
        raise ValueError(f"a peça {ident!r} não se marca")
    if tela.e_reinstalacao(item):
        _reinstalar().symmetric_difference_update({ident})
    else:
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
    """«Tentar de novo»: a fila viva roda de novo as que falharam; sem fila, abre outra."""
    ids = [str(x.get("id")) for x in at.ler_o_andamento().get("pecas") or []
           if isinstance(x, dict) and x.get("selo") == at.FALHOU]
    if not ids:
        raise ValueError("tentar: nenhuma peça falhou")
    if at.em_curso():
        at.pedir_para_tentar(ids)
    elif not at.soltar(ids):
        raise RuntimeError("tentar: a fila não abriu")
    TELA["escondida"] = 0.0
    _repintar()


TETO_DO_REGISTRO = 64 * 1024


def _o_registro() -> str:
    try:
        dado = at.caminho_do_registro().read_bytes()
    except OSError:
        return ""
    return dado[-TETO_DO_REGISTRO:].decode("utf-8", "replace")


@gesto("*", "atualizacoes-registro")
def registro(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Registro»: o registro desta atualização dentro da caixa."""
    TELA["vista"] = "registro"
    _repintar()


@gesto("*", "atualizacoes-registro-voltar")
def registro_voltar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    TELA["vista"] = "andamento"
    TELA["escondida"] = 0.0
    _repintar()


@gesto("*", "atualizacoes-registro-copiar")
def registro_copiar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    from hefesto_dualsense4unix.utils import area_de_transferencia

    if not area_de_transferencia.por(_o_registro()):
        raise RuntimeError("registro: a área de transferência não aceitou")


@gesto("*", "atualizacoes-registro-salvar", grava="salva o registro da atualização")
def registro_salvar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    from gi.repository import GLib

    destino = Path(os.environ.get("XDG_DOWNLOAD_DIR")
                   or GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
                   or Path.home() / "Downloads")
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"hefesto-atualizacao-{time.strftime('%Y-%m-%d-%H%M%S')}.log"
    arquivo.write_text(_o_registro(), encoding="utf-8")


@gesto("*", "atualizacoes-continuar", grava="continua a atualização parada")
def continuar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Continuar»: a fila parada abre de novo com as peças que não terminaram."""
    ids = [str(x.get("id")) for x in at.ler_o_andamento().get("pecas") or []
           if isinstance(x, dict) and x.get("selo") not in (at.PRONTA, at.ATUALIZADA)]
    if not ids:
        raise ValueError("continuar: nada ficou para trás")
    if not at.soltar(ids):
        raise RuntimeError("continuar: a fila não abriu")
    TELA["escondida"] = 0.0
    _repintar()


@gesto("*", "atualizacoes-fechar-a-steam", grava="fecha a Steam para a atualização seguir")
def fechar_a_steam(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    at.pedir_para_fechar_a_steam()
    _repintar()


@gesto("*", "atualizacoes-reiniciar-o-computador")
def perguntar_o_reinicio(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Reiniciar o computador»: só abre a pergunta; quem reinicia é o «Reiniciar» da pergunta."""
    TELA["vista"] = "reiniciar"
    _repintar()


@gesto("*", "atualizacoes-nao-reiniciar")
def nao_reiniciar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Agora não» da pergunta do reinício: a caixa volta ao fim como estava."""
    if TELA["vista"] == "reiniciar":
        TELA["vista"] = "andamento"
    _repintar()


@gesto("*", "atualizacoes-confirmar-o-reinicio", grava="reinicia o computador")
def reiniciar_o_computador(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Reiniciar» da pergunta: reinicia só com a pergunta aberta, e a desarma antes."""
    from hefesto_dualsense4unix.app.actions.daemon_actions import prazo_do_systemctl

    if not _a_pergunta_do_reinicio_aberta():
        raise ValueError("reiniciar: a pergunta do reinício não está aberta")
    TELA["vista"] = "andamento"
    _repintar()
    feito = subprocess.run(["systemctl", "reboot"], check=False, capture_output=True,
                           text=True, timeout=prazo_do_systemctl(["reboot"]))
    if feito.returncode != 0:
        raise RuntimeError(f"reiniciar: {feito.stderr.strip() or feito.returncode}")


PISO_DA_ABA = 15
PONTE: set[str] = set()
METODOS: set[str] = set()
