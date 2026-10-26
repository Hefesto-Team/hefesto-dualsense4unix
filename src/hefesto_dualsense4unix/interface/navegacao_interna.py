"""A Navegação Interna na janela: dos toques de cada controle aos atos da tela.

A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01, com o desenho dela
de 03/10/2026: com a Interna ligada e a janela na frente, cada controle anda as
abas com R1 e L1, anda a SUA seleção com o direcional, o analógico esquerdo ou o
touchpad, aciona com X, sai com O e guarda o perfil de todos com Start.

Este módulo é puro: recebe os contadores que o daemon devolve no
``navegacao.foco`` (``toques``), o ``inputs`` de cada controle e o leiaute que a
página mede, e devolve atos e operações. Quem os executa é o ``hefesto_vivo``;
quem os mede é a régua, sem WebKit.

OS TOQUES SÃO CONTADORES QUE SÓ SOBEM. Aqui se aplica a diferença com o que se
leu antes: um R1 curto entre dois tiques anda uma aba, o que o nível do botão
(``inputs.buttons``) perderia.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

PREFIXOS_DA_VOLTA = ("01", "02", "03", "04", "05")

LIMIAR_DO_ANALOGICO = 64
REPETICAO_DO_ANALOGICO_S = 0.25

DIRECOES = ("cima", "baixo", "esquerda", "direita")

PRAZO_DO_DONO_S = 3.0


@dataclass(frozen=True)
class Ato:
    """Um ato da janela: ``ir``, ``salvar``, ``fechar`` ou um da seleção."""

    tipo: str
    pagina: str = ""
    uniq: str = ""
    direcao: str = ""
    ponto: tuple[float, float] | None = None


@dataclass(frozen=True)
class Caixa:
    """Um elemento que se seleciona, como a página o mediu."""

    endereco: str
    x: float
    y: float
    largura: float
    altura: float
    tipo: str = ""
    dono: str = ""

    @property
    def centro(self) -> tuple[float, float]:
        return self.x + self.largura / 2, self.y + self.altura / 2

    def contem(self, px: float, py: float) -> bool:
        return (self.x <= px <= self.x + self.largura
                and self.y <= py <= self.y + self.altura)


def abas_da_volta(paginas: Iterable[str]) -> tuple[str, ...]:
    """As abas por controle, na ordem da barra (o prefixo de dois dígitos)."""
    return tuple(sorted(p for p in paginas if p[:2] in PREFIXOS_DA_VOLTA))


def aba_seguinte(pagina: str, passo: int, abas: Sequence[str],
                 dez: Sequence[str]) -> str | None:
    """A aba depois de um R1 (``passo=1``) ou de um L1 (``passo=-1``).

    Dentro das cinco, dá a volta. De uma das outras abas, o R1 entra pela
    primeira e o L1 pela última. Fora das dez (o mapa, as portas, a
    calibração) não anda: a porta dali é o «Voltar».
    """
    if not abas or pagina not in dez:
        return None
    if pagina in abas:
        return abas[(abas.index(pagina) + passo) % len(abas)]
    return abas[0] if passo > 0 else abas[-1]


def vizinho(caixas: Sequence[Caixa], atual: int | None, direcao: str) -> int | None:
    """O índice da caixa mais perto de ``atual`` naquela direção, pela geometria.

    Entra quem está do lado pedido (o centro além do centro de agora); vence
    o menor passo no eixo da direção somado ao dobro do desvio no outro eixo,
    e, no empate, o mais alinhado de centro a centro. O desvio é de borda a
    borda, zero quando as caixas se cobrem no outro eixo: a caixa da frente, na
    faixa da de agora, nunca é pulada (a lista larga sob o interruptor estreito).
    Sem seleção, a primeira da leitura (de cima para baixo, da esquerda para a direita).
    """
    if not caixas:
        return None
    if atual is None or not 0 <= atual < len(caixas):
        return min(range(len(caixas)),
                   key=lambda i: (caixas[i].y, caixas[i].x))
    a = caixas[atual]
    ax, ay = a.centro
    melhor: tuple[float, float] | None = None
    escolhido: int | None = None
    for i, c in enumerate(caixas):
        if i == atual:
            continue
        cx, cy = c.centro
        if direcao in ("cima", "baixo"):
            frente = ay - cy if direcao == "cima" else cy - ay
            lado = max(0.0, c.x - (a.x + a.largura), a.x - (c.x + c.largura))
            alinhado = abs(cx - ax)
        else:
            frente = ax - cx if direcao == "esquerda" else cx - ax
            lado = max(0.0, c.y - (a.y + a.altura), a.y - (c.y + c.altura))
            alinhado = abs(cy - ay)
        if frente <= 0.5:
            continue
        chave = (frente + 2 * lado, alinhado)
        if melhor is None or chave < melhor:
            melhor, escolhido = chave, i
    return escolhido


def sob_o_dedo(caixas: Sequence[Caixa], px: float, py: float) -> int | None:
    """A caixa sob o ponto; sem nenhuma, a de centro mais perto."""
    if not caixas:
        return None
    for i, c in enumerate(caixas):
        if c.contem(px, py):
            return i
    return min(range(len(caixas)),
               key=lambda i: math.dist(caixas[i].centro, (px, py)))


def ponto_do_dedo(inputs: Mapping[str, Any] | None) -> tuple[float, float] | None:
    """O dedo no touchpad, de 0 a 1 em cada eixo, ou ``None`` sem toque."""
    toque = (inputs or {}).get("touchpad")
    if not isinstance(toque, Mapping) or not toque.get("touching"):
        return None
    largura = float(toque.get("width") or 0)
    altura = float(toque.get("height") or 0)
    if largura <= 0 or altura <= 0:
        return None
    fx = min(1.0, max(0.0, float(toque.get("x") or 0) / largura))
    fy = min(1.0, max(0.0, float(toque.get("y") or 0) / altura))
    return fx, fy


def direcao_do_analogico(inputs: Mapping[str, Any] | None) -> str:
    """Para onde o analógico esquerdo aponta além do limiar, ou vazio."""
    inputs = inputs or {}
    lx, ly = inputs.get("lx"), inputs.get("ly")
    dx = 0 if lx is None else int(lx) - 128
    dy = 0 if ly is None else int(ly) - 128
    if max(abs(dx), abs(dy)) < LIMIAR_DO_ANALOGICO:
        return ""
    if abs(dx) >= abs(dy):
        return "direita" if dx > 0 else "esquerda"
    return "baixo" if dy > 0 else "cima"


@dataclass
class _Analogico:
    direcao: str = ""
    proximo: float = 0.0


@dataclass
class Navegador:
    """Os toques de cada controle viram atos, uma vez cada."""

    relogio: Callable[[], float] = time.monotonic
    _vistos: dict[str, dict[str, int]] = field(default_factory=dict)
    _analogicos: dict[str, _Analogico] = field(default_factory=dict)
    _dono: str = ""
    _dono_ate: float = float("-inf")

    def _diferenca(self, toques: Mapping[str, Mapping[str, int]]) -> dict[str, dict[str, int]]:
        novos: dict[str, dict[str, int]] = {}
        for uniq, contas in toques.items():
            if not isinstance(contas, Mapping):
                continue
            antes = self._vistos.get(uniq)
            agora = {k: int(v or 0) for k, v in contas.items()}
            self._vistos[uniq] = agora
            if antes is None:
                continue
            novos[uniq] = {
                k: (v - antes.get(k, 0) if v >= antes.get(k, 0) else v)
                for k, v in agora.items()
            }
        return novos

    def atos(
        self,
        *,
        pagina: str,
        dez: Sequence[str],
        toques: Mapping[str, Mapping[str, int]],
        ativa: bool,
        inputs: Mapping[str, Mapping[str, Any]] | None = None,
        sem_selecao: Iterable[str] = (),
    ) -> list[Ato]:
        """Os atos deste tique. A janela inativa só ressincroniza a base."""
        novos = self._diferenca(toques)
        if not ativa:
            self._analogicos.clear()
            self._dono = ""
            return []
        fora = set(sem_selecao)
        agora = self.relogio()
        salvar = any(d.get("start", 0) > 0 for d in novos.values())
        dono = self._o_dono(sorted(set(novos) | set(inputs or {})), novos, inputs or {}, fora,
                            agora)
        novos = {dono: novos[dono]} if dono in novos else {}
        atos: list[Ato] = []
        aba = pagina
        abas = abas_da_volta(dez)
        for uniq in sorted(novos):
            d = novos[uniq]
            for passo, nome in ((1, "r1"), (-1, "l1")):
                for _ in range(max(0, d.get(nome, 0))):
                    seguinte = aba_seguinte(aba, passo, abas, dez)
                    if seguinte is not None:
                        aba = seguinte
        if aba != pagina:
            atos.append(Ato("ir", pagina=aba))
        if salvar:
            atos.append(Ato("salvar"))
        for uniq in sorted(set(novos) | set(inputs or {})):
            if uniq in fora or uniq != dono:
                self._analogicos.pop(uniq, None)
                continue
            d = novos.get(uniq, {})
            for direcao in DIRECOES:
                atos.extend(Ato("passo", uniq=uniq, direcao=direcao)
                            for _ in range(max(0, d.get(direcao, 0))))
            atos.extend(self._do_analogico(uniq, (inputs or {}).get(uniq), agora))
            ponto = ponto_do_dedo((inputs or {}).get(uniq))
            if ponto is not None:
                atos.append(Ato("dedo", uniq=uniq, ponto=ponto))
            atos.extend(Ato("x", uniq=uniq) for _ in range(max(0, d.get("x", 0))))
            atos.extend(Ato("o", uniq=uniq) for _ in range(max(0, d.get("o", 0))))
        return atos

    def _o_dono(self, uniqs: Sequence[str], novos: Mapping[str, Mapping[str, int]],
                inputs: Mapping[str, Mapping[str, Any]], fora: set[str], agora: float) -> str:
        """Quem navega neste tique, ou vazio: o dono segue até ficar ``PRAZO_DO_DONO_S`` parado
        (ou sair), e só então o primeiro que mexer assume. O toque de quem não é dono se perde."""

        def mexeu(uniq: str) -> bool:
            if any(n > 0 for k, n in novos.get(uniq, {}).items() if k != "start"):
                return True
            if uniq in fora:
                return False
            entrada = inputs.get(uniq)
            return bool(direcao_do_analogico(entrada)) or ponto_do_dedo(entrada) is not None

        if self._dono and (agora > self._dono_ate or self._dono not in uniqs):
            self._dono = ""
        if not self._dono:
            self._dono = next((u for u in uniqs if mexeu(u)), "")
        if self._dono and mexeu(self._dono):
            self._dono_ate = agora + PRAZO_DO_DONO_S
        return self._dono

    def _do_analogico(self, uniq: str, inputs: Mapping[str, Any] | None,
                      agora: float) -> list[Ato]:
        direcao = direcao_do_analogico(inputs)
        estado = self._analogicos.setdefault(uniq, _Analogico())
        if not direcao:
            estado.direcao = ""
            return []
        if direcao != estado.direcao or agora >= estado.proximo:
            estado.direcao = direcao
            estado.proximo = agora + REPETICAO_DO_ANALOGICO_S
            return [Ato("passo", uniq=uniq, direcao=direcao)]
        return []


@dataclass
class _Selecao:
    endereco: str = ""
    dentro: bool = False


@dataclass
class Selecoes:
    """A seleção de cada controle, pelo ``uniq``, e o que cada ato pede à página.

    As operações devolvidas são dicionários que o ``__hef.nav`` da página
    executa: ``clicar`` (com o assento de quem apertou, para a fita escolher
    antes), ``escolha`` e ``trilho`` (um passo dentro de uma lista ou de um
    trilho) e ``fechar`` (a pop-up aberta).
    """

    _de: dict[str, _Selecao] = field(default_factory=dict)

    def de(self, uniq: str) -> str:
        sel = self._de.get(uniq)
        return sel.endereco if sel is not None else ""

    def alguma(self) -> bool:
        """Algum controle tem seleção (e a moldura dele se redesenha)."""
        return any(sel.endereco for sel in self._de.values())

    def dentro(self, uniq: str) -> bool:
        sel = self._de.get(uniq)
        return bool(sel and sel.dentro)

    def esquecer_quem_saiu(self, presentes: Iterable[str]) -> None:
        """Controle que sai perde a seleção; o que volta começa no primeiro."""
        ficam = set(presentes)
        for uniq in list(self._de):
            if uniq not in ficam:
                del self._de[uniq]

    def aplicar(
        self,
        atos: Sequence[Ato],
        caixas_de: Callable[[str], Sequence[Caixa]],
        *,
        pref_de: Mapping[str, str],
        popup: bool,
    ) -> list[dict[str, Any]]:
        """Aplica os atos da seleção e devolve as operações para a página."""
        ops: list[dict[str, Any]] = []
        for ato in atos:
            if ato.tipo not in ("passo", "dedo", "x", "o"):
                continue
            uniq = ato.uniq
            caixas = caixas_de(uniq)
            sel = self._de.setdefault(uniq, _Selecao())
            enderecos = [c.endereco for c in caixas]
            if sel.endereco not in enderecos:
                sel.endereco, sel.dentro = "", False
            atual = enderecos.index(sel.endereco) if sel.endereco else None
            if ato.tipo == "o":
                if sel.dentro:
                    sel.dentro = False
                elif popup:
                    ops.append({"op": "fechar"})
                continue
            if ato.tipo == "x":
                if atual is None:
                    continue
                caixa = caixas[atual]
                if sel.dentro:
                    sel.dentro = False
                elif caixa.tipo in ("lista", "trilho"):
                    sel.dentro = True
                else:
                    ops.append({"op": "clicar", "endereco": caixa.endereco,
                                "pref": pref_de.get(uniq, "")})
                continue
            if sel.dentro and atual is not None and ato.tipo == "passo":
                caixa = caixas[atual]
                eixo = (("cima", "baixo") if caixa.tipo == "lista"
                        else ("esquerda", "direita"))
                if ato.direcao in eixo:
                    ops.append({"op": "escolha" if caixa.tipo == "lista" else "trilho",
                                "endereco": caixa.endereco,
                                "passo": 1 if ato.direcao == eixo[1] else -1})
                continue
            if ato.tipo == "dedo" and ato.ponto is not None:
                indice = sob_o_dedo(caixas, *ato.ponto)
            else:
                indice = vizinho(caixas, atual, ato.direcao)
            if indice is not None:
                sel.endereco, sel.dentro = caixas[indice].endereco, False
        return ops

    def molduras(self, pref_de: Mapping[str, str],
                 cor_de: Mapping[str, str]) -> list[dict[str, Any]]:
        """O que a página desenha: a moldura de cada seleção, na cor do plástico."""
        return [
            {"endereco": sel.endereco, "pref": pref_de.get(uniq, ""),
             "cor": cor_de.get(uniq, ""), "dentro": sel.dentro}
            for uniq, sel in sorted(self._de.items(), key=lambda kv: pref_de.get(kv[0], ""))
            if sel.endereco
        ]


def caixas_do_leiaute(leiaute: Mapping[str, Any], pref: str) -> list[Caixa]:
    """As caixas que o controle de assento ``pref`` seleciona.

    O desenho dela de 03/10: cada um ajusta o seu. Entram o que mora no bloco
    dele e o que não mora no bloco de controle nenhum; o do vizinho, não.
    O ponto do dedo vem de 0 a 1, e a caixa em pixels: quem chama converte.
    """
    caixas: list[Caixa] = []
    for c in leiaute.get("caixas") or []:
        if not isinstance(c, Mapping):
            continue
        dono = str(c.get("dono") or "")
        if dono and dono != pref:
            continue
        caixas.append(Caixa(
            endereco=str(c.get("endereco") or ""),
            x=float(c.get("x") or 0), y=float(c.get("y") or 0),
            largura=float(c.get("w") or 0), altura=float(c.get("h") or 0),
            tipo=str(c.get("tipo") or ""), dono=dono))
    return [c for c in caixas if c.endereco]


def no_espaco_da_pagina(atos: Sequence[Ato], leiaute: Mapping[str, Any]) -> list[Ato]:
    """O ponto do dedo (0 a 1) passa aos pixels da página medida."""
    largura = float(leiaute.get("largura") or 0)
    altura = float(leiaute.get("altura") or 0)
    fora: list[Ato] = []
    for ato in atos:
        if ato.tipo == "dedo" and ato.ponto is not None:
            ato = Ato("dedo", uniq=ato.uniq, ponto=(ato.ponto[0] * largura,
                                                     ato.ponto[1] * altura))
        fora.append(ato)
    return fora
