"""O atualizador: cada peça de fora na versão mais nova publicada, uma por vez, sem jogo aberto.

O motor conhece as peças pelo registro (:mod:`pecas_do_atualizador`), cada uma com a versão
instalada, a publicada e os passos baixar, instalar e aplicar em todos. A fila roda num processo
próprio, fora da janela (``--rodar``), e escreve o andamento num arquivo que a janela lê a cada
tique: o serviço reinicia no fim, e a tela não pode depender dele para saber onde a fila está.

A escolha das peças, o «Atualizar sozinho», o prazo da pergunta e a versão que se voltou
(segurada, para não subir de novo) moram no ``atualizador.json`` da configuração. Antes de
instalar, a versão de agora vai para as anteriores, que é o que «Versões anteriores» lista.
"""
from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import json
import os
import re
import sys
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MODULO = "hefesto_dualsense4unix.app.actions.atualizador"
ARQUIVO_DA_ESCOLHA = "atualizador.json"
ARQUIVO_DA_CONFERENCIA = "atualizador-conferencia.json"
ARQUIVO_DO_ANDAMENTO = "atualizador-andamento.json"
ARQUIVO_DAS_ANTERIORES = "atualizador-anteriores.json"
REGISTRO = "atualizador.log"
TRAVA = "atualizador.trava"
PEDIDO_DE_PARAR = "atualizador.parar"
DIAS_PADRAO = 7
DIAS_MINIMO = 1
DIAS_MAXIMO = 90
DIA_S = 86400.0
ESPERA_DO_DEV_S = 30.0

ETAPAS = ("baixar", "instalar", "aplicar")
FAIXA_DA_ETAPA = {"baixar": (0.0, 40.0), "instalar": (40.0, 80.0), "aplicar": (80.0, 100.0)}
ETAPAS_DO_SERVICO = ("reiniciar", "reabrir")

NOVA = "nova"
EM_DIA = "em_dia"
NAO_CONSULTADO = "nao_consultado"
FIXA = "fixa"
FORA = "fora"

FILA = "fila"
BAIXANDO = "baixando"
INSTALANDO = "instalando"
APLICANDO = "aplicando"
PRONTA = "pronta"
FALHOU = "falhou"
REINICIANDO = "reiniciando"
SELO_DA_ETAPA = {"baixar": BAIXANDO, "instalar": INSTALANDO, "aplicar": APLICANDO}

ANDANDO = "andando"
ESPERA_O_JOGO = "espera_o_jogo"
FIM = "fim"
PARADO = "parado"


class EtapaFalhouError(Exception):
    """A etapa não se fez; a mensagem é o porquê, que a dica da peça mostra."""


class FilaParadaError(Exception):
    """Quem usa pediu para parar: a fila sai entre duas etapas, nunca no meio de uma."""


def ordem(versao: str) -> tuple[tuple[int, int | str], ...]:
    """A versão por partes: número com número, nunca como texto (``5.9`` antes de ``5.10``)."""
    return tuple((1, int(p)) if p.isdigit() else (0, p.lower())
                 for p in re.findall(r"\d+|[A-Za-z]+", versao or ""))


@dataclass(frozen=True)
class Versoes:
    """O que a peça tem e o que saiu. ``publicada`` ``None``: a fonte não respondeu."""

    instalada: str = ""
    publicada: str | None = None
    rotulo: str = ""
    dica: str = ""
    nova: bool | None = None
    existe: bool = True

    def tem_nova(self) -> bool:
        if self.nova is not None:
            return self.nova
        if not self.publicada or self.publicada == self.instalada:
            return False
        return not self.instalada or ordem(self.publicada) > ordem(self.instalada)


@dataclass
class Passo:
    """O que uma etapa de uma peça diz ao motor: a fração da etapa, as contagens e o registro."""

    aviso: Callable[[], None] = lambda: None
    fracao_: float = 0.0
    contagens: dict[str, tuple[int, int]] = field(default_factory=dict)
    linhas: list[str] = field(default_factory=list)

    def fracao(self, valor: float) -> None:
        self.fracao_ = max(0.0, min(1.0, float(valor)))
        self.aviso()

    def contagem(self, qual: str, feitos: int, de: int) -> None:
        self.contagens[qual] = (max(0, int(feitos)), max(0, int(de)))
        self.aviso()

    def dizer(self, linha: str) -> None:
        self.linhas.append(linha)
        _anotar(linha)


Etapa = Callable[[Passo, dict[str, Any]], dict[str, Any] | None]


@dataclass(frozen=True)
class Peca:
    """Uma peça de fora. ``volta`` 2: a tela a mostra, e o motor ainda não a sobe."""

    id: str
    nome: str
    dica: str
    dica_do_aplicar: str
    versoes: Callable[[bool], Versoes]
    baixar: Etapa | None = None
    instalar: Etapa | None = None
    aplicar: Etapa | None = None
    voltar: Callable[[dict[str, Any]], None] | None = None
    grupo: str = "infra"
    volta: int = 1
    marcada_por_padrao: bool = True


def pecas() -> list[Peca]:
    from hefesto_dualsense4unix.app.actions import pecas_do_atualizador

    return pecas_do_atualizador.registro()


def _por_id(lista: Iterable[Peca]) -> dict[str, Peca]:
    return {p.id: p for p in lista}


def _config() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    return config_dir(ensure=True)


def _estado() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir(ensure=True)


def _runtime() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

    return runtime_dir(ensure=True)


def _ler_json(caminho: Path) -> dict[str, Any]:
    try:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dado if isinstance(dado, dict) else {}


def _gravar_json(caminho: Path, dado: dict[str, Any]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(f".{caminho.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(dado, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(caminho)


def _anotar(linha: str) -> None:
    with contextlib.suppress(OSError), (_estado() / REGISTRO).open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {linha}\n")


def caminho_do_registro() -> Path:
    return _estado() / REGISTRO


@dataclass
class Escolha:
    """O que quem usa escolheu: as peças marcadas, o «Atualizar sozinho» e o prazo."""

    sozinho: bool = False
    dias: int = DIAS_PADRAO
    marcadas: dict[str, bool] = field(default_factory=dict)
    perguntada_em: float = 0.0
    seguradas: dict[str, str] = field(default_factory=dict)

    def marcada(self, peca: Peca) -> bool:
        return bool(self.marcadas.get(peca.id, peca.marcada_por_padrao)) and peca.volta == 1


def ler_a_escolha() -> Escolha:
    dado = _ler_json(_config() / ARQUIVO_DA_ESCOLHA)
    try:
        dias = int(dado.get("dias", DIAS_PADRAO))
    except (TypeError, ValueError):
        dias = DIAS_PADRAO
    try:
        perguntada = float(dado.get("perguntada_em", 0.0) or 0.0)
    except (TypeError, ValueError):
        perguntada = 0.0
    marcadas = dado.get("marcadas")
    seguradas = dado.get("seguradas")
    return Escolha(
        sozinho=bool(dado.get("sozinho", False)),
        dias=max(DIAS_MINIMO, min(DIAS_MAXIMO, dias)),
        marcadas={str(k): bool(v) for k, v in marcadas.items()} if isinstance(marcadas, dict)
        else {},
        perguntada_em=perguntada,
        seguradas={str(k): str(v) for k, v in seguradas.items()} if isinstance(seguradas, dict)
        else {},
    )


def gravar_a_escolha(escolha: Escolha) -> None:
    _gravar_json(_config() / ARQUIVO_DA_ESCOLHA, dataclasses.asdict(escolha))


def mudar_a_escolha(*, sozinho: bool | None = None, dias: int | None = None,
                    peca: str | None = None, marcada: bool | None = None,
                    perguntada_em: float | None = None) -> Escolha:
    """Muda só o que veio, e grava. Os dias ficam entre 1 e 90."""
    escolha = ler_a_escolha()
    if sozinho is not None:
        escolha.sozinho = bool(sozinho)
    if dias is not None:
        escolha.dias = max(DIAS_MINIMO, min(DIAS_MAXIMO, int(dias)))
    if peca is not None and marcada is not None:
        escolha.marcadas[peca] = bool(marcada)
    if perguntada_em is not None:
        escolha.perguntada_em = float(perguntada_em)
    gravar_a_escolha(escolha)
    return escolha


def prazo_vencido(escolha: Escolha, agora: float) -> bool:
    return agora - escolha.perguntada_em >= escolha.dias * DIA_S


def _estado_da_peca(peca: Peca, versoes: Versoes, escolha: Escolha) -> str:
    if not versoes.existe:
        return FORA
    if peca.volta != 1:
        return FIXA
    if versoes.publicada is None:
        return NAO_CONSULTADO
    if versoes.tem_nova() and escolha.seguradas.get(peca.id) != versoes.publicada:
        return NOVA
    return EM_DIA


def conferir(rede: bool = True, *, lista: Sequence[Peca] | None = None,
             agora: Callable[[], float] = time.time) -> dict[str, Any]:
    """O vigia: a versão instalada e a publicada de cada peça. Sem rede, «não consultado».

    Uma peça que levanta não derruba as outras: fica «não consultado», com o porquê.
    """
    escolha = ler_a_escolha()
    itens: list[dict[str, Any]] = []
    for peca in (pecas() if lista is None else lista):
        try:
            versoes = peca.versoes(rede)
        except Exception as erro:
            versoes = Versoes(dica=str(erro) or type(erro).__name__)
        estado = _estado_da_peca(peca, versoes, escolha)
        itens.append({
            "id": peca.id, "nome": peca.nome, "grupo": peca.grupo, "volta": peca.volta,
            "dica": versoes.dica or peca.dica, "dica_do_aplicar": peca.dica_do_aplicar,
            "de": versoes.instalada, "para": versoes.publicada or "",
            "rotulo": versoes.rotulo, "estado": estado,
            "marcada": escolha.marcada(peca),
            "pode_voltar": peca.voltar is not None,
        })
    conferencia = {"em": agora(), "rede": rede, "pecas": itens}
    _gravar_json(_estado() / ARQUIVO_DA_CONFERENCIA, conferencia)
    return conferencia


def ler_a_conferencia() -> dict[str, Any]:
    return _ler_json(_estado() / ARQUIVO_DA_CONFERENCIA)


def novas(conferencia: dict[str, Any], escolha: Escolha | None = None,
          *, so_marcadas: bool = True) -> list[str]:
    """As peças com versão nova, na ordem do registro; ``so_marcadas`` aplica a escolha."""
    escolha = ler_a_escolha() if escolha is None else escolha
    saida = []
    for item in conferencia.get("pecas") or []:
        if not isinstance(item, dict) or item.get("estado") != NOVA:
            continue
        if so_marcadas and not escolha.marcadas.get(str(item.get("id")),
                                                    bool(item.get("marcada", True))):
            continue
        saida.append(str(item.get("id")))
    return saida


def ler_as_anteriores() -> dict[str, Any]:
    return _ler_json(_estado() / ARQUIVO_DAS_ANTERIORES)


def ler_o_andamento() -> dict[str, Any]:
    return _ler_json(_estado() / ARQUIVO_DO_ANDAMENTO)


def marcar_o_andamento_visto() -> None:
    """O fim que quem usa fechou não volta na próxima abertura."""
    andamento = ler_o_andamento()
    if andamento:
        _gravar_json(_estado() / ARQUIVO_DO_ANDAMENTO, {**andamento, "visto": True})


def total(andamento: dict[str, Any]) -> dict[str, Any]:
    """A linha «Total»: quantas prontas de quantas, a média das barras e quantas falharam."""
    itens = [p for p in andamento.get("pecas") or [] if isinstance(p, dict)]
    if not itens:
        return {"feitas": 0, "de": 0, "pct": 0, "falhas": 0}
    feitas = sum(1 for p in itens if p.get("selo") == PRONTA)
    falhas = sum(1 for p in itens if p.get("selo") == FALHOU)
    pct = sum(float(p.get("pct", 0) or 0) for p in itens) / len(itens)
    return {"feitas": feitas, "de": len(itens), "pct": round(pct), "falhas": falhas}


class _Andamento:
    """O arquivo do andamento, regravado inteiro a cada mudança (troca atômica)."""

    def __init__(self, lista: Sequence[Peca], versoes: dict[str, Versoes]) -> None:
        self.dado: dict[str, Any] = {
            "fase": ANDANDO, "inicio": time.time(), "pid": os.getpid(),
            "pecas": [{
                "id": p.id, "nome": p.nome, "de": versoes[p.id].instalada,
                "para": versoes[p.id].publicada or "", "rotulo": versoes[p.id].rotulo,
                "dica_do_aplicar": p.dica_do_aplicar,
                "etapas": dict.fromkeys(ETAPAS, ""), "pct": 0, "selo": FILA, "motivo": "",
                "contagens": [],
            } for p in lista],
            "reinicio": {"etapas": dict.fromkeys(ETAPAS_DO_SERVICO, ""), "pct": 0, "selo": FILA},
        }
        self._ultimo = 0.0
        self.gravar()

    def peca(self, ident: str) -> dict[str, Any]:
        return next(p for p in self.dado["pecas"] if p["id"] == ident)

    def gravar(self, *, ja: bool = True) -> None:
        agora = time.monotonic()
        if not ja and agora - self._ultimo < 0.25:
            return
        self._ultimo = agora
        self.dado["total"] = total(self.dado)
        with contextlib.suppress(OSError):
            _gravar_json(_estado() / ARQUIVO_DO_ANDAMENTO, self.dado)


def _pediram_parar() -> bool:
    return (_runtime() / PEDIDO_DE_PARAR).exists()


def pedir_para_parar() -> None:
    with contextlib.suppress(OSError):
        (_runtime() / PEDIDO_DE_PARAR).write_text(str(time.time()), encoding="utf-8")


def _a_trava() -> int | None:
    try:
        fd = os.open(_runtime() / TRAVA, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as erro:
        _anotar(f"a trava não abre: {erro}")
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def em_curso() -> bool:
    """Há uma fila rodando agora? A trava cai com o processo que a tomou."""
    fd = _a_trava()
    if fd is None:
        return True
    os.close(fd)
    return False


def _jogo_aberto() -> bool:
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import _jogo_aberto as perguntar

    return perguntar()


def _esperar_sem_jogo(andamento: _Andamento, jogo_aberto: Callable[[], bool],
                      relogio: Callable[[], float], dormir: Callable[[float], None],
                      prazo_s: float) -> bool:
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import (
        PASSO_DA_VIGIA_S,
        EsperaSemJogo,
    )

    espera = EsperaSemJogo()
    inicio = relogio()
    primeiro = True
    while relogio() - inicio < prazo_s:
        aberto = jogo_aberto()
        if primeiro and not aberto:
            return True
        primeiro = False
        if espera.fechou_de_vez(aberto, relogio()):
            andamento.dado["fase"] = ANDANDO
            andamento.gravar()
            return True
        if aberto and andamento.dado["fase"] != ESPERA_O_JOGO:
            andamento.dado["fase"] = ESPERA_O_JOGO
            andamento.gravar()
        if _pediram_parar():
            raise FilaParadaError
        dormir(PASSO_DA_VIGIA_S)
    return False


def _guardar_a_anterior(peca: Peca, versoes: Versoes, dados: dict[str, Any],
                        agora: float) -> None:
    anteriores = ler_as_anteriores()
    anteriores[peca.id] = {"nome": peca.nome, "agora": versoes.publicada or "",
                           "anterior": versoes.instalada, "desde": agora, "dados": dados}
    _gravar_json(_estado() / ARQUIVO_DAS_ANTERIORES, anteriores)


def _devolver_a_anterior(ident: str, antes: Any) -> None:
    anteriores = ler_as_anteriores()
    if antes is None:
        anteriores.pop(ident, None)
    else:
        anteriores[ident] = antes
    _gravar_json(_estado() / ARQUIVO_DAS_ANTERIORES, anteriores)


def _rodar_a_peca(peca: Peca, versoes: Versoes, andamento: _Andamento,
                  agora: Callable[[], float]) -> None:
    linha = andamento.peca(peca.id)
    dados: dict[str, Any] = {}
    antes = ler_as_anteriores().get(peca.id)
    for etapa in ETAPAS:
        if _pediram_parar():
            raise FilaParadaError
        fazer = getattr(peca, etapa)
        inicio, fim = FAIXA_DA_ETAPA[etapa]
        linha["etapas"][etapa] = "agora"
        linha["selo"] = SELO_DA_ETAPA[etapa]
        linha["pct"] = round(inicio)
        andamento.gravar()

        def avisar(passo: Passo, inicio: float = inicio, fim: float = fim) -> None:
            linha["pct"] = round(inicio + (fim - inicio) * passo.fracao_)
            linha["contagens"] = [{"qual": q, "feitos": n, "de": d}
                                  for q, (n, d) in passo.contagens.items()]
            andamento.gravar(ja=False)

        passo = Passo()
        passo.aviso = lambda p=passo: avisar(p)
        try:
            if etapa == "instalar":
                _guardar_a_anterior(peca, versoes, dados, agora())
            if fazer is not None:
                volta = fazer(passo, dados)
                if volta:
                    dados.update(volta)
        except EtapaFalhouError as erro:
            linha["etapas"][etapa] = "erro"
            linha["selo"] = FALHOU
            linha["motivo"] = str(erro)
            _anotar(f"{peca.id}: {etapa} falhou: {erro}")
            if etapa == "instalar":
                _devolver_a_anterior(peca.id, antes)
            andamento.gravar()
            return
        except FilaParadaError:
            raise
        except Exception as erro:
            motivo = str(erro) or type(erro).__name__
            linha["etapas"][etapa] = "erro"
            linha["selo"] = FALHOU
            linha["motivo"] = motivo
            _anotar(f"{peca.id}: {etapa} levantou: {motivo}")
            if etapa == "instalar":
                _devolver_a_anterior(peca.id, antes)
            andamento.gravar()
            return
        linha["etapas"][etapa] = "feito"
        linha["pct"] = round(fim)
        andamento.gravar()
    if dados:
        anteriores = ler_as_anteriores()
        if peca.id in anteriores:
            anteriores[peca.id]["dados"] = dados
            _gravar_json(_estado() / ARQUIVO_DAS_ANTERIORES, anteriores)
    linha["selo"] = PRONTA
    _anotar(f"{peca.id}: {versoes.instalada} -> {versoes.publicada} pronta")
    andamento.gravar()


def _reiniciar_o_servico() -> bool:
    from hefesto_dualsense4unix.app.actions import troca_no_fim_do_jogo as troca

    return "daemon" in troca.aplicar(("broker", "daemon"))


def _reabrir_o_hefesto() -> bool:
    from hefesto_dualsense4unix.app.actions.recarga_do_install import recarregar

    return not any("não" in frase for frase in recarregar())


def _rodar_o_servico(andamento: _Andamento, reiniciar: Callable[[], bool],
                     reabrir: Callable[[], bool]) -> None:
    reinicio = andamento.dado["reinicio"]
    for etapa, fazer, pct in (("reiniciar", reiniciar, 50), ("reabrir", reabrir, 100)):
        reinicio["etapas"][etapa] = "agora"
        reinicio["selo"] = REINICIANDO
        andamento.gravar()
        try:
            feito = fazer()
        except Exception as erro:
            _anotar(f"serviço: {etapa} levantou: {erro}")
            feito = False
        reinicio["etapas"][etapa] = "feito" if feito else "erro"
        reinicio["pct"] = pct
        if not feito:
            reinicio["selo"] = FALHOU
            andamento.gravar()
            return
        andamento.gravar()
    reinicio["selo"] = PRONTA


def rodar(
    ids: Sequence[str],
    *,
    lista: Sequence[Peca] | None = None,
    jogo_aberto: Callable[[], bool] = _jogo_aberto,
    reiniciar: Callable[[], bool] = _reiniciar_o_servico,
    reabrir: Callable[[], bool] = _reabrir_o_hefesto,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
    agora: Callable[[], float] = time.time,
    prazo_do_jogo_s: float | None = None,
) -> int:
    """A fila: uma peça por vez, cada uma em baixar, instalar e aplicar em todos.

    Um processo por vez (o segundo sai com 3). Com jogo aberto, espera ele fechar de vez antes
    de cada peça; no prazo, sai como «parado». Uma peça que falha não para as outras. No fim,
    reinicia o serviço e reabre a janela. Devolve 0 com tudo pronto, 1 com alguma falha.
    """
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import PRAZO_DA_VIGIA_S

    trava = _a_trava()
    if trava is None:
        return 3
    try:
        with contextlib.suppress(OSError):
            (_runtime() / PEDIDO_DE_PARAR).unlink()
        registro = _por_id(pecas() if lista is None else lista)
        escolhidas = [registro[i] for i in dict.fromkeys(ids)
                      if i in registro and registro[i].volta == 1]
        versoes: dict[str, Versoes] = {}
        conferencia = {str(item.get("id")): item
                       for item in ler_a_conferencia().get("pecas") or []
                       if isinstance(item, dict)}
        for peca in escolhidas:
            visto = conferencia.get(peca.id)
            versoes[peca.id] = (Versoes(str(visto.get("de", "")), str(visto.get("para", "")),
                                        rotulo=str(visto.get("rotulo", "")))
                                if visto else Versoes())
        andamento = _Andamento(escolhidas, versoes)
        _anotar(f"fila: {', '.join(p.id for p in escolhidas) or 'nada'}")
        prazo = PRAZO_DA_VIGIA_S if prazo_do_jogo_s is None else prazo_do_jogo_s
        try:
            for peca in escolhidas:
                if not _esperar_sem_jogo(andamento, jogo_aberto, relogio, dormir, prazo):
                    raise FilaParadaError
                _rodar_a_peca(peca, versoes[peca.id], andamento, agora)
            if not _esperar_sem_jogo(andamento, jogo_aberto, relogio, dormir, prazo):
                raise FilaParadaError
            andamento.dado["fase"] = FIM
            andamento.gravar()
            if escolhidas:
                _rodar_o_servico(andamento, reiniciar, reabrir)
        except FilaParadaError:
            andamento.dado["fase"] = PARADO
            _anotar("fila: parada")
            andamento.gravar()
            return 2
        andamento.dado["fase"] = FIM
        andamento.gravar()
        with contextlib.suppress(OSError):
            conferir(rede=True, lista=lista)
        return 1 if andamento.dado["total"]["falhas"] else 0
    finally:
        os.close(trava)


def voltar(ident: str, *, lista: Sequence[Peca] | None = None) -> str:
    """Volta a peça à versão anterior e segura a que saiu. Devolve o porquê, ou vazio."""
    registro = _por_id(pecas() if lista is None else lista)
    peca = registro.get(ident)
    anterior = ler_as_anteriores().get(ident)
    if peca is None or peca.voltar is None:
        return "a peça não volta"
    if not isinstance(anterior, dict) or not anterior.get("anterior"):
        return "sem versão anterior"
    try:
        peca.voltar(anterior)
    except EtapaFalhouError as erro:
        return str(erro)
    escolha = ler_a_escolha()
    escolha.seguradas[ident] = str(anterior.get("agora", ""))
    gravar_a_escolha(escolha)
    anteriores = ler_as_anteriores()
    anteriores.pop(ident, None)
    _gravar_json(_estado() / ARQUIVO_DAS_ANTERIORES, anteriores)
    _anotar(f"{ident}: voltou a {anterior.get('anterior')}")
    return ""


def soltar(ids: Sequence[str], *, abrir: Callable[..., Any] | None = None) -> bool:
    """Abre a fila numa unidade própria, que a janela não leva quando fecha. Diz se soltou."""
    from hefesto_dualsense4unix.integrations import fora_do_servico
    from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo

    if not ids or (abrir is None and em_curso()):
        return False
    try:
        (abrir or fora_do_servico.abrir)(
            [sys.executable, "-m", MODULO, "--rodar", *ids],
            env=ambiente_limpo(os.environ), aplicativo="atualizador")
    except OSError:
        return False
    return True


def conferir_ao_abrir(fio_do_dev: threading.Thread | None = None, *,
                      soltar_: Callable[[Sequence[str]], bool] = soltar,
                      agora: Callable[[], float] = time.time) -> threading.Thread:
    """O vigia da abertura, num fio: confere, e com «Atualizar sozinho» no prazo, solta a fila.

    Espera o fio que traz o ``dev`` (a peça Hefesto lê o que ele baixou), sem passar do teto.
    """
    def _conferir() -> None:
        if fio_do_dev is not None:
            fio_do_dev.join(ESPERA_DO_DEV_S)
        try:
            conferencia = conferir(rede=True)
        except Exception as erro:
            _anotar(f"vigia: {erro}")
            return
        escolha = ler_a_escolha()
        if escolha.sozinho and prazo_vencido(escolha, agora()) and not em_curso():
            ids = novas(conferencia, escolha)
            if ids and soltar_(ids):
                mudar_a_escolha(perguntada_em=agora())

    fio = threading.Thread(target=_conferir, name="atualizador-vigia", daemon=True)
    fio.start()
    return fio


def hora_da_pergunta(agora: float | None = None) -> bool:
    """A janela abre a pergunta? Sem «Atualizar sozinho», no prazo, com peça nova."""
    escolha = ler_a_escolha()
    if escolha.sozinho or em_curso():
        return False
    momento = time.time() if agora is None else agora
    return prazo_vencido(escolha, momento) and bool(
        novas(ler_a_conferencia(), escolha, so_marcadas=False))


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--rodar"]:
        return rodar(args[1:])
    if args[:1] == ["--conferir"]:
        conferencia = conferir(rede="--sem-rede" not in args)
        for item in conferencia["pecas"]:
            print(f"{item['nome']}: {item['de'] or item['rotulo'] or '—'} -> "
                  f"{item['para'] or '—'} ({item['estado']})")
        return 0
    if args[:1] == ["--voltar"] and len(args) == 2:
        motivo = voltar(args[1])
        if motivo:
            print(motivo, file=sys.stderr)
            return 1
        return 0
    if args[:1] == ["--parar"]:
        pedir_para_parar()
        return 0
    print("uso: --conferir [--sem-rede] | --rodar <peça>... | --voltar <peça> | --parar",
          file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
