"""O atualizador: cada peça de fora na versão mais nova publicada, uma por vez, sem jogo aberto.

O motor lê as peças do registro (:mod:`pecas_do_atualizador`): versões e os passos baixar,
instalar e aplicar; a peça em dia reinstala a de agora (:class:`Reinstalacao`). A fila roda num
processo próprio (``--rodar``) e escreve o andamento que a janela lê a cada tique. A escolha, o
prazo e a versão segurada moram no ``atualizador.json``; a versão de agora vai às anteriores.

Cada peça termina Atualizado (instalou, ou nada a fazer), Esperando (a Steam, o jogo, o voo: a
fila segue e volta a essa peça quando passa) ou Falhou (o erro de verdade). O andamento de um
processo que morreu no meio se encerra ao ler.
"""
from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import functools
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
ARQUIVO_DO_QUE_JA_ESTA = "atualizador-ja-esta.json"
REGISTRO = "atualizador.log"
TRAVA = "atualizador.trava"
PEDIDO_DE_PARAR = "atualizador.parar"
PEDIDO_DE_TENTAR = "atualizador.tentar"
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
REVISAR = "revisar"
REINSTALAM = (EM_DIA, REVISAR)

FILA = "fila"
BAIXANDO = "baixando"
INSTALANDO = "instalando"
APLICANDO = "aplicando"
PRONTA = "pronta"
FALHOU = "falhou"
REINICIANDO = "reiniciando"
ESPERANDO = "esperando"
ATUALIZADA = "atualizada"
ACABADAS = (PRONTA, ATUALIZADA)
EM_CURSO = (BAIXANDO, INSTALANDO, APLICANDO, ESPERANDO, REINICIANDO)
O_JOGO_ABERTO = "o jogo aberto"
SELO_DA_ETAPA = {"baixar": BAIXANDO, "instalar": INSTALANDO, "aplicar": APLICANDO}

SUBIR = "subir"
REINSTALAR = "reinstalar"
NAO_SE_REINSTALA = "esta peça não se reinstala pela janela"

ANDANDO = "andando"
ESPERA_O_JOGO = "espera_o_jogo"
ESPERA = "espera"
VIVAS = (ANDANDO, ESPERA_O_JOGO, ESPERA)
FIM = "fim"
PARADO = "parado"


class EtapaFalhouError(Exception):
    """A etapa não se fez; a mensagem é o porquê, que a dica da peça mostra."""


class FilaParadaError(Exception):
    """Quem usa pediu para parar: a fila sai entre duas etapas, nunca no meio de uma."""


class EsperaError(Exception):
    """A etapa ainda não pode, e não é falha: a mensagem diz o que se espera, e ``livre`` diz quando
    passou. A fila segue com as outras peças e volta a esta da mesma etapa."""

    def __init__(self, motivo: str, livre: Callable[[], bool]) -> None:
        super().__init__(motivo)
        self.livre = livre


class NadaAFazerError(Exception):
    """A peça já está como devia (a versão de cima já traz a cura): fica «Atualizado», e a mesma
    versão não se oferece de novo."""


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
    completa: str = ""
    revisar: str = ""

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
class Reinstalacao:
    """A versão que está na máquina, de novo; ``por_que_nao`` vazio: reinstala, senão o porquê."""

    baixar: Etapa | None = None
    instalar: Etapa | None = None
    aplicar: Etapa | None = None
    por_que_nao: Callable[[Versoes], str] | None = None


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
    reinstalacao: Reinstalacao | None = None
    anterior: Callable[[], dict[str, Any] | None] | None = None


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
    """O que quem usa escolheu: as peças marcadas, a «Atualização automática» e o prazo."""

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


def _chave_do_que_ja_esta(versoes: Versoes) -> str:
    return versoes.completa or versoes.publicada or ""


def _ler_o_que_ja_esta() -> dict[str, Any]:
    return _ler_json(_estado() / ARQUIVO_DO_QUE_JA_ESTA)


def _ja_esta(peca: Peca, versoes: Versoes, ja: dict[str, Any]) -> str:
    """O porquê de a versão nova não ter o que fazer aqui, se a fila já viu; vazio senão."""
    visto = ja.get(peca.id)
    if not isinstance(visto, dict) or visto.get("chave") != _chave_do_que_ja_esta(versoes):
        return ""
    return str(visto.get("motivo") or "")


def _guardar_o_que_ja_esta(peca: Peca, versoes: Versoes, motivo: str) -> None:
    ja = _ler_o_que_ja_esta()
    ja[peca.id] = {"chave": _chave_do_que_ja_esta(versoes), "motivo": motivo}
    _gravar_json(_estado() / ARQUIVO_DO_QUE_JA_ESTA, ja)


def _estado_da_peca(peca: Peca, versoes: Versoes, escolha: Escolha,
                    ja: dict[str, Any] | None = None) -> str:
    if not versoes.existe:
        return FORA
    if peca.volta != 1:
        return FIXA
    if versoes.revisar:
        return REVISAR
    if versoes.publicada is None:
        return NAO_CONSULTADO
    if versoes.tem_nova() and escolha.seguradas.get(peca.id) != versoes.publicada \
            and not _ja_esta(peca, versoes, {} if ja is None else ja):
        return NOVA
    return EM_DIA


def _sem_reinstalar(peca: Peca, versoes: Versoes, estado: str) -> str:
    """Vazio se a peça em dia ou a revisar reinstala; o porquê senão. Só essas se perguntam."""
    if peca.reinstalacao is None:
        return NAO_SE_REINSTALA
    if estado not in REINSTALAM or peca.reinstalacao.por_que_nao is None:
        return ""
    try:
        return peca.reinstalacao.por_que_nao(versoes)
    except Exception as erro:
        return str(erro) or type(erro).__name__


def conferir(rede: bool = True, *, lista: Sequence[Peca] | None = None,
             agora: Callable[[], float] = time.time) -> dict[str, Any]:
    """O vigia: a versão instalada e a publicada de cada peça. Sem rede, «não consultado».

    Uma peça que levanta não derruba as outras: fica «não consultado», com o porquê.
    """
    escolha = ler_a_escolha()
    ja = _ler_o_que_ja_esta()
    itens: list[dict[str, Any]] = []
    for peca in (pecas() if lista is None else lista):
        try:
            versoes = peca.versoes(rede)
        except Exception as erro:
            versoes = Versoes(dica=str(erro) or type(erro).__name__)
        estado = _estado_da_peca(peca, versoes, escolha, ja)
        motivo = _sem_reinstalar(peca, versoes, estado)
        itens.append({
            "id": peca.id, "nome": peca.nome, "grupo": peca.grupo, "volta": peca.volta,
            "dica": versoes.revisar or _ja_esta(peca, versoes, ja) or versoes.dica or peca.dica,
            "dica_do_aplicar": peca.dica_do_aplicar,
            "de": versoes.instalada, "para": versoes.publicada or "",
            "completa": versoes.completa, "rotulo": versoes.rotulo, "estado": estado,
            "marcada": escolha.marcada(peca),
            "pode_voltar": peca.voltar is not None,
            "reinstala": not motivo, "motivo": motivo,
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


def anteriores_a_mostrar(lista: Sequence[Peca] | None = None) -> dict[str, Any]:
    """As anteriores que voltam; a peça com registro próprio da anterior lê o próprio registro."""
    anteriores = ler_as_anteriores()
    for peca in (pecas() if lista is None else lista):
        if peca.anterior is None:
            continue
        try:
            propria = peca.anterior()
        except Exception as erro:
            _anotar(f"{peca.id}: a anterior não se leu: {erro}")
            propria = None
        if propria:
            anteriores[peca.id] = propria
        else:
            anteriores.pop(peca.id, None)
    return anteriores


def _encerrar_o_orfao(andamento: dict[str, Any]) -> dict[str, Any]:
    """O andamento que diz «andando» sem fila viva: o processo morreu no meio, e ninguém o termina.

    Fica «parado» e visto, com o que estava em curso de volta à fila: a tela não espera por ele, e
    o mapa volta a dizer o que há para atualizar.
    """
    pecas = [p for p in andamento.get("pecas") or [] if isinstance(p, dict)]
    for linha in pecas:
        if linha.get("selo") in EM_CURSO:
            linha["selo"] = FILA
        etapas = linha.get("etapas")
        if isinstance(etapas, dict):
            linha["etapas"] = {k: ("" if v == "agora" else v) for k, v in etapas.items()}
    reinicio = andamento.get("reinicio")
    if isinstance(reinicio, dict) and reinicio.get("selo") in EM_CURSO:
        reinicio["selo"] = FILA
    encerrado = {**andamento, "pecas": pecas, "fase": PARADO, "visto": True, "fim_em": time.time()}
    encerrado["total"] = total(encerrado)
    with contextlib.suppress(OSError):
        _gravar_json(_estado() / ARQUIVO_DO_ANDAMENTO, encerrado)
    _anotar(f"fila: o processo {andamento.get('pid', '?')} saiu no meio; o andamento se encerrou")
    return encerrado


def ler_o_andamento() -> dict[str, Any]:
    andamento = _ler_json(_estado() / ARQUIVO_DO_ANDAMENTO)
    if andamento.get("fase") in VIVAS and not em_curso():
        return _encerrar_o_orfao(andamento)
    return andamento


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
    feitas = sum(1 for p in itens if p.get("selo") in ACABADAS)
    falhas = sum(1 for p in itens if p.get("selo") == FALHOU)
    pct = sum(float(p.get("pct", 0) or 0) for p in itens) / len(itens)
    return {"feitas": feitas, "de": len(itens), "pct": round(pct), "falhas": falhas}


class _Andamento:
    """O arquivo do andamento, regravado inteiro a cada mudança (troca atômica)."""

    def __init__(self, lista: Sequence[Peca], versoes: dict[str, Versoes],
                 o_que_fazer: dict[str, str]) -> None:
        self.dado: dict[str, Any] = {
            "fase": ANDANDO, "inicio": time.time(), "pid": os.getpid(),
            "pecas": [{
                "id": p.id, "nome": p.nome, "de": versoes[p.id].instalada,
                "para": versoes[p.id].publicada or "", "rotulo": versoes[p.id].rotulo,
                "fazer": o_que_fazer[p.id],
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


def pedir_para_tentar(ids: Sequence[str]) -> None:
    _gravar_json(_runtime() / PEDIDO_DE_TENTAR, {"ids": list(ids)})


def _pedido_de_tentar() -> list[str]:
    caminho = _runtime() / PEDIDO_DE_TENTAR
    ids = _ler_json(caminho).get("ids")
    with contextlib.suppress(OSError):
        caminho.unlink()
    return [str(i) for i in ids] if isinstance(ids, list) else []


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
                      prazo_s: float, linha: dict[str, Any] | None = None) -> bool:
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import (
        PASSO_DA_VIGIA_S,
        EsperaSemJogo,
    )

    espera = EsperaSemJogo()
    inicio = relogio()
    primeiro = True
    antes = (linha.get("selo"), linha.get("motivo")) if linha is not None else None
    while primeiro or relogio() - inicio < prazo_s:
        aberto = jogo_aberto()
        if primeiro and not aberto:
            return True
        primeiro = False
        if espera.fechou_de_vez(aberto, relogio()):
            andamento.dado["fase"] = ANDANDO
            if linha is not None and antes is not None:
                linha["selo"], linha["motivo"] = antes
            andamento.gravar()
            return True
        if aberto and andamento.dado["fase"] != ESPERA_O_JOGO:
            andamento.dado["fase"] = ESPERA_O_JOGO
            if linha is not None:
                linha["selo"], linha["motivo"] = ESPERANDO, O_JOGO_ABERTO
            andamento.gravar()
        if _pediram_parar():
            raise FilaParadaError
        dormir(PASSO_DA_VIGIA_S)
    return False


def _guardar_a_anterior(peca: Peca, versoes: Versoes, dados: dict[str, Any],
                        agora: float) -> None:
    anteriores = ler_as_anteriores()
    anteriores[peca.id] = {"nome": peca.nome, "agora": versoes.publicada or "",
                           "anterior": versoes.instalada, "rotulo": versoes.rotulo,
                           "desde": agora, "dados": dados}
    _gravar_json(_estado() / ARQUIVO_DAS_ANTERIORES, anteriores)


def _devolver_a_anterior(ident: str, antes: Any) -> None:
    anteriores = ler_as_anteriores()
    if antes is None:
        anteriores.pop(ident, None)
    else:
        anteriores[ident] = antes
    _gravar_json(_estado() / ARQUIVO_DAS_ANTERIORES, anteriores)


@dataclass
class _Vez:
    """O que a peça carrega entre uma espera e a volta: a etapa de onde segue e os dados."""

    dados: dict[str, Any] = field(default_factory=dict)
    desde: int = 0
    antes: Any = None


def _rodar_a_peca(peca: Peca, versoes: Versoes, andamento: _Andamento,
                  agora: Callable[[], float], vez: _Vez | None = None) -> EsperaError | None:
    """Baixar, instalar e aplicar, da etapa em que a peça parou. Devolve a espera, se esperou."""
    linha = andamento.peca(peca.id)
    vez = _Vez(antes=ler_as_anteriores().get(peca.id)) if vez is None else vez
    dados = vez.dados
    reinstala = linha["fazer"] == REINSTALAR
    fonte: Any = peca.reinstalacao if reinstala else peca
    linha["motivo"] = ""
    for indice, etapa in enumerate(ETAPAS):
        if indice < vez.desde:
            continue
        if _pediram_parar():
            raise FilaParadaError
        fazer = getattr(fonte, etapa)
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
        passo.aviso = functools.partial(avisar, passo)
        guardou = etapa == "instalar" and not reinstala
        try:
            if guardou:
                _guardar_a_anterior(peca, versoes, dados, agora())
            if fazer is not None:
                volta = fazer(passo, dados)
                if volta:
                    dados.update(volta)
        except FilaParadaError:
            raise
        except EsperaError as espera:
            if guardou:
                _devolver_a_anterior(peca.id, vez.antes)
            linha["etapas"][etapa] = ""
            linha["selo"] = ESPERANDO
            linha["motivo"] = str(espera)
            linha["pct"] = round(inicio)
            vez.desde = indice
            _anotar(f"{peca.id}: {etapa} espera: {espera}")
            andamento.gravar()
            return espera
        except NadaAFazerError as nada:
            if guardou:
                _devolver_a_anterior(peca.id, vez.antes)
            _atualizada(peca, versoes, linha, str(nada), etapa=etapa, guardar=not reinstala)
            andamento.gravar()
            return None
        except Exception as erro:
            motivo = str(erro) or type(erro).__name__
            linha["etapas"][etapa] = "erro"
            linha["selo"] = FALHOU
            linha["motivo"] = motivo
            _anotar(f"{peca.id}: {etapa} "
                    f"{'falhou' if isinstance(erro, EtapaFalhouError) else 'levantou'}: {motivo}")
            if guardou:
                _devolver_a_anterior(peca.id, vez.antes)
            andamento.gravar()
            return None
        linha["etapas"][etapa] = "feito"
        linha["pct"] = round(fim)
        andamento.gravar()
    if dados and not reinstala:
        anteriores = ler_as_anteriores()
        if peca.id in anteriores:
            anteriores[peca.id]["dados"] = dados
            _gravar_json(_estado() / ARQUIVO_DAS_ANTERIORES, anteriores)
    linha["selo"] = PRONTA
    _anotar(f"{peca.id}: {versoes.instalada} reinstalada" if reinstala
            else f"{peca.id}: {_de_para(versoes)} pronta")
    andamento.gravar()
    return None


def _de_para(versoes: Versoes) -> str:
    if versoes.rotulo and not versoes.instalada:
        return versoes.rotulo
    return f"{versoes.instalada or '—'} -> {versoes.publicada or '—'}"


def _atualizada(peca: Peca, versoes: Versoes, linha: dict[str, Any], motivo: str, *,
                etapa: str = "", guardar: bool = True) -> None:
    """A peça sem nada a fazer: «Atualizado», e a mesma versão não se oferece de novo."""
    for chave in ETAPAS:
        if linha["etapas"].get(chave) == "agora" or chave == etapa:
            linha["etapas"][chave] = ""
    linha["selo"] = ATUALIZADA
    linha["motivo"] = motivo
    linha["pct"] = 100
    if guardar and motivo and versoes.publicada:
        _guardar_o_que_ja_esta(peca, versoes, motivo)
    _anotar(f"{peca.id}: nada a fazer ({motivo})" if motivo else f"{peca.id}: já está em dia")


def _ainda_em_dia(peca: Peca, visto: dict[str, Any] | None) -> bool:
    """A peça que ia subir, conferida de novo na sua vez: já está na versão nova?"""
    try:
        versoes = peca.versoes(True)
    except Exception:
        return False
    if versoes.publicada is None or not versoes.existe:
        return False
    return _estado_da_peca(peca, versoes, ler_a_escolha(), _ler_o_que_ja_esta()) == EM_DIA \
        and not (visto and visto.get("estado") == REVISAR)


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
    andamento.gravar()


def _o_que_fazer(peca: Peca, visto: dict[str, Any] | None) -> str:
    """Subir, reinstalar ou nada: a peça em dia ou a revisar reinstala só se a conferência disse
    que pode, e a revisar nunca sobe."""
    if not visto or visto.get("estado") not in REINSTALAM:
        return SUBIR
    if peca.reinstalacao is None or not visto.get("reinstala"):
        _anotar(f"{peca.id}: não se reinstala ({visto.get('motivo') or '—'})")
        return ""
    return REINSTALAR


def _prontas(andamento: _Andamento) -> set[str]:
    return {str(p.get("id")) for p in andamento.dado["pecas"] if p.get("selo") == PRONTA}


def _livre(espera: EsperaError) -> bool:
    try:
        return bool(espera.livre())
    except Exception as erro:
        _anotar(f"a espera não respondeu: {erro}")
        return False


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
    """A fila: uma peça por vez, em baixar, instalar e aplicar em todos; um processo por vez (o
    segundo sai com 3). A em dia reinstala; a que ia subir se confere de novo na sua vez (e ao fim
    da espera, se ainda não começou) e, já em dia, fica «Atualizado» sem baixar. A que espera (a
    Steam, o voo) vai para o fim e volta da mesma etapa quando passa. Com jogo aberto, espera ele
    fechar de vez antes de cada peça. Uma falha não para as outras. Se alguma peça mudou,
    reinicia o serviço e reabre a janela: antes de esperar a que ficou para trás (o código novo
    não roda horas sob o serviço velho) e de novo se a peça mudar. Devolve 0 pronto, 1 com falha,
    2 parada ou com peça ainda esperando.
    """
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import (
        PASSO_DA_VIGIA_S,
        PRAZO_DA_VIGIA_S,
    )

    trava = _a_trava()
    if trava is None:
        return 3
    try:
        for pedido in (PEDIDO_DE_PARAR, PEDIDO_DE_TENTAR):
            with contextlib.suppress(OSError):
                (_runtime() / pedido).unlink()
        registro = _por_id(pecas() if lista is None else lista)
        conferencia = {str(item.get("id")): item
                       for item in ler_a_conferencia().get("pecas") or []
                       if isinstance(item, dict)}
        o_que_fazer = {i: _o_que_fazer(registro[i], conferencia.get(i)) for i in dict.fromkeys(ids)
                 if i in registro and registro[i].volta == 1}
        escolhidas = [registro[i] for i, fazer in o_que_fazer.items() if fazer]
        versoes: dict[str, Versoes] = {}
        for peca in escolhidas:
            visto = conferencia.get(peca.id)
            de = str(visto.get("de", "")) if visto else ""
            para = de if o_que_fazer[peca.id] == REINSTALAR else (
                str(visto.get("para", "")) if visto else "")
            versoes[peca.id] = Versoes(de, para, rotulo=str(visto.get("rotulo", "")),
                                       completa=str(visto.get("completa", ""))) \
                if visto else Versoes()
        andamento = _Andamento(escolhidas, versoes, o_que_fazer)
        _anotar(f"fila: {', '.join(p.id for p in escolhidas) or 'nada'}")
        limite = relogio() + (PRAZO_DA_VIGIA_S if prazo_do_jogo_s is None else prazo_do_jogo_s)

        def prazo() -> float:
            return limite - relogio()

        adiadas: list[tuple[Peca, EsperaError, _Vez]] = []

        def _recolher_o_pedido_de_tentar() -> None:
            for ident in _pedido_de_tentar():
                if ident not in versoes or andamento.peca(ident).get("selo") != FALHOU:
                    continue
                linha = andamento.peca(ident)
                linha["selo"], linha["motivo"] = FILA, ""
                linha["etapas"] = dict.fromkeys(ETAPAS, "")
                _anotar(f"{ident}: de novo, a pedido")
                adiadas.append((registro[ident], EsperaError("", lambda: True),
                                _Vez(antes=ler_as_anteriores().get(ident))))

        def _ja_subiu(peca: Peca, linha: dict[str, Any]) -> bool:
            """A peça que ia subir, conferida antes de começar: em dia, fica «Atualizado»."""
            if o_que_fazer[peca.id] != SUBIR or not _ainda_em_dia(peca, conferencia.get(peca.id)):
                return False
            _atualizada(peca, versoes[peca.id], linha, "", guardar=False)
            andamento.gravar()
            return True

        try:
            for peca in escolhidas:
                linha = andamento.peca(peca.id)
                if not _esperar_sem_jogo(andamento, jogo_aberto, relogio, dormir, prazo(), linha):
                    raise FilaParadaError
                if _ja_subiu(peca, linha):
                    continue
                vez = _Vez(antes=ler_as_anteriores().get(peca.id))
                espera = _rodar_a_peca(peca, versoes[peca.id], andamento, agora, vez)
                if espera is not None:
                    adiadas.append((peca, espera, vez))
            reiniciadas: set[str] = set()
            if adiadas and _prontas(andamento):
                if not _esperar_sem_jogo(andamento, jogo_aberto, relogio, dormir, prazo()):
                    raise FilaParadaError
                _rodar_o_servico(andamento, reiniciar, reabrir)
                reiniciadas = _prontas(andamento)
            _recolher_o_pedido_de_tentar()
            while adiadas and prazo() > 0:
                if _pediram_parar():
                    raise FilaParadaError
                ainda: list[tuple[Peca, EsperaError, _Vez]] = []
                for peca, espera, vez in adiadas:
                    if not _livre(espera):
                        ainda.append((peca, espera, vez))
                        continue
                    andamento.dado["fase"] = ANDANDO
                    linha = andamento.peca(peca.id)
                    if not _esperar_sem_jogo(andamento, jogo_aberto, relogio, dormir, prazo(),
                                             linha):
                        raise FilaParadaError
                    if vez.desde == 0 and _ja_subiu(peca, linha):
                        continue
                    outra = _rodar_a_peca(peca, versoes[peca.id], andamento, agora, vez)
                    if outra is not None:
                        ainda.append((peca, outra, vez))
                adiadas = ainda
                if adiadas and andamento.dado["fase"] != ESPERA:
                    andamento.dado["fase"] = ESPERA
                    andamento.dado["espera"] = {"peca": adiadas[0][0].id,
                                                "motivo": str(adiadas[0][1]), "desde": agora(),
                                                "ate": agora() + max(0.0, prazo())}
                    andamento.gravar()
                if adiadas:
                    dormir(PASSO_DA_VIGIA_S)
                _recolher_o_pedido_de_tentar()
            for peca, espera, _vez in adiadas:
                linha = andamento.peca(peca.id)
                linha["selo"], linha["motivo"] = FILA, str(espera)
                _anotar(f"{peca.id}: a espera passou do prazo ({espera}); fica para a próxima")
            if not _esperar_sem_jogo(andamento, jogo_aberto, relogio, dormir, prazo()):
                raise FilaParadaError
            andamento.dado["fase"], andamento.dado["fim_em"] = FIM, agora()
            andamento.gravar()
            if _prontas(andamento) - reiniciadas:
                _rodar_o_servico(andamento, reiniciar, reabrir)
            elif not reiniciadas:
                andamento.dado["reinicio"]["selo"] = ATUALIZADA
        except FilaParadaError:
            andamento.dado["fase"], andamento.dado["fim_em"] = PARADO, agora()
            for linha in andamento.dado["pecas"]:
                if linha.get("selo") in EM_CURSO:
                    linha["selo"] = FILA
            _anotar("fila: parada")
            andamento.gravar()
            return 2
        andamento.dado["fase"] = FIM
        andamento.dado.setdefault("fim_em", agora())
        andamento.gravar()
        with contextlib.suppress(OSError):
            conferir(rede=True, lista=lista)
        if andamento.dado["total"]["falhas"]:
            return 1
        return 2 if adiadas else 0
    finally:
        os.close(trava)


def voltar(ident: str, *, lista: Sequence[Peca] | None = None) -> str:
    """Volta a peça à versão anterior e segura a que saiu. Devolve o porquê, ou vazio."""
    registro = _por_id(pecas() if lista is None else lista)
    peca = registro.get(ident)
    anterior = anteriores_a_mostrar(list(registro.values())).get(ident)
    if peca is None or peca.voltar is None:
        return "a peça não volta"
    if not isinstance(anterior, dict) or not (anterior.get("anterior") or anterior.get("rotulo")):
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
    """O vigia da abertura, num fio: encerra o andamento órfão, confere, e com «Atualização
    automática» no prazo, solta a fila.

    Espera o fio que traz o ``dev`` (a peça Hefesto lê o que ele baixou), sem passar do teto.
    """
    def _conferir() -> None:
        if fio_do_dev is not None:
            fio_do_dev.join(ESPERA_DO_DEV_S)
        try:
            ler_o_andamento()
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
    """A janela abre a pergunta? Sem «Atualização automática», no prazo, com peça nova."""
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
    from hefesto_dualsense4unix.app.actions import atualizador as _o_modulo_das_pecas

    raise SystemExit(_o_modulo_das_pecas.main())
