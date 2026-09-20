#!/usr/bin/env python3
"""catraca.py — O MOTOR DA CATRACA, e ele é UM SÓ.

O QUE É UMA CATRACA NESTA CASA
-------------------------------
Uma catraca **nunca pede mutirão**. Ela sabe o número de HOJE, grava-o num
caderno versionado, e recusa que ele SUBA. O acervo antigo é problema de quem
for dono dele; a catraca cobra só de quem está escrevendo a linha nova, no
momento em que a escreve. É assim que o custo some — não porque alguém pagou de
uma vez, mas porque ninguém mais acrescentou.

A palavra é dela, e é o desenho inteiro:

    "Um Hook que vá facilitando isso seria maravilhoso. Pois organicamente   (noqa-acento: citação literal dela)
     deixaríamos fácil pra gente e pro outro"

POR QUE O MOTOR É SEPARADO DAS MEDIDAS
---------------------------------------
Duas implementações da mesma catraca é o defeito que esta casa já nomeou e
pagou: *a lista de portões vivia em dois lugares — o contrato da casa e o
`ci.yml` — e as duas divergiam*. Então há **um motor** e **N medidas**: quem
precisar de uma catraca nova registra a função que conta e não escreve laço,
caderno, nem comparação nenhuma.

Quem chega primeiro escreve o motor; o segundo IMPORTA. **Medido em 20/09/2026,
antes de escrever uma linha:** a `PODA-DO-DATADO-01` ainda não tinha aterrissado
(`scripts/catraca.py` não existia na árvore), então quem escreveu foi a
`TRADUZIR-O-PROJETO-01`. Quem vier depois importa isto e não escreve motor
nenhum — registrar a própria medida custa uma :class:`Medida`. A receita, para
quem vier de `scripts/`::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from catraca import Catraca, Censo, Medida

AS QUATRO ARMADILHAS QUE ESTE MOTOR EXISTE PARA NÃO TER
--------------------------------------------------------
Cada uma é um defeito medido nesta casa, e cada uma tem mordida no teste.

1. **A trava que se mede contra a própria saída não trava nada.** Medido em
   07/09/2026: a régua que devia impedir o CSV de perder colunas comparava o
   arquivo novo com ELE MESMO, e passou verde enquanto o mapa perdia 50. Aqui,
   ``comparar()`` lê o caderno do DISCO antes de medir e **nunca escreve**.
   Quem grava é ``aceitar()`` ou ``forcar_piso()``, que são atos separados, com
   nome próprio e com razão escrita.

2. **O conjunto vazio nunca é a resposta certa.** Medido em quatro instrumentos
   diferentes: *o portão escolhia a venv pela POSIÇÃO*; *as pastas mudaram de
   nome e as réguas não foram junto*; *lote montado da árvore ERRADA morre
   calado, e `no tests ran` lê-se como limpo*; *o `--prova-gesto` nunca clicava
   o botão do microfone*. Toda medida declara o UNIVERSO que varreu, e universo
   vazio — ou menor do que a própria medida sabe exigir — é **VERMELHO**, nunca
   o zero que se lê como verde.

3. **Zero se lê como verde.** Uma medida que ainda não pode medir (porque o
   dado de que ela depende não existe) devolveria zero, e zero passa. Por isso
   existe o estado ``PENDENTE``: o piso grava a palavra, com a razão escrita, e
   o motor **se recusa a comparar**. ``PENDENTE`` nunca vira ``VERDE``.

4. **Instrumento que sabe do próprio risco RESOLVE, não avisa.** Uma medida
   pendente que ACORDA — o dado apareceu — não fica calada esperando alguém
   reparar: o motor reprova dizendo que a medida passou a medir e que o piso
   tem de ser gravado. E uma medida com piso numérico que PARA de poder medir
   reprova igual, porque piso sobre o que não se mede é piso falso.

O CADERNO
---------
JSON versionado, um por conjunto de medidas, no formato::

    {
      "medidas": {
        "<nome>": {
          "piso": 1234 | "PENDENTE",
          "data": "AAAA-MM-DD",
          "razao": "por que este é o piso",
          "universo": 2468,
          "por_item": {"caminho/ou/chave": 123, ...},
          "bruto": {"censo_de_hoje": 3311},        # só quando PENDENTE
          "subidas":   [{"data":…, "de":…, "para":…, "razao":…}]
        }
      }
    }

``por_item`` é o que permite dizer **O QUE ENTROU** em vez de só o número — e
isso não é enfeite: *um número vermelho sem o nome faz a pessoa procurar, e
procurar é o que desliga portão.*
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

PENDENTE = "PENDENTE"

# Os estados de um veredito. VERDE é o único que passa; PENDENTE passa a
# execução mas NÃO é verde, e a diferença é o item 3 do cabeçalho.
VERDE = "VERDE"
VERMELHO = "VERMELHO"
ESTADO_PENDENTE = "PENDENTE"
IMPOSSIVEL = "IMPOSSIVEL"
SEM_PISO = "SEM-PISO"


class CatracaTorta(Exception):
    """O motor foi usado de um jeito que esconde defeito. Estoura, não avisa."""


@dataclass(frozen=True)
class Censo:
    """O resultado de uma medida: o número, o que o compõe, e o que foi varrido.

    ``numero`` é ``None`` — e só ``None`` — quando a medida **não pode medir**.
    Devolver ``0`` nesse caso é o defeito do item 3 do cabeçalho, e o motor
    estoura se as duas coisas não combinarem.

    ``universo`` é o tamanho do corpo varrido (arquivos abertos, páginas
    encontradas). É por ele que a mordida do vazio reprova: contar zero num
    universo de zero não é medir, é não ter olhado.
    """

    numero: int | None
    universo: int
    por_item: dict[str, int] = field(default_factory=dict)
    nomes: tuple[str, ...] = ()
    indisponivel: str | None = None
    bruto: dict[str, int] = field(default_factory=dict)
    nota: str = ""

    def __post_init__(self) -> None:
        if (self.numero is None) != (self.indisponivel is not None):
            raise CatracaTorta(
                "Censo torto: `numero=None` e `indisponivel` andam juntos. "
                "Uma medida que não pode medir devolve None E a razão; uma que "
                "pode devolve o número E nenhuma razão. Devolver 0 sem razão "
                "sobre o que não se mediu é verde sobre nada."
            )


@dataclass(frozen=True)
class Medida:
    """Uma coisa que se conta e não pode subir.

    ``censo`` recebe a raiz da árvore e devolve um :class:`Censo`. Recebe a
    raiz — em vez de fechá-la por closure — justamente para que a mordida do
    vazio possa apontar a medida para uma pasta vazia sem mexer no fonte.

    ``conferir_universo`` é a segunda peneira do vazio, e é onde cada medida
    diz o que ELA sabe exigir do próprio corpo. Devolve a queixa, ou "" quando
    o universo é plausível. O motor já reprova universo ZERO sozinho; esta é
    para o caso mais fino — dez páginas que viraram sete.
    """

    nome: str
    o_que_conta: str
    censo: Callable[[Path], Censo]
    unidade: str = "unidades"
    conferir_universo: Callable[[Path, Censo], str] | None = None


@dataclass(frozen=True)
class Piso:
    """O piso lido do caderno. ``numero is None`` significa ``PENDENTE``."""

    numero: int | None
    data: str
    razao: str
    por_item: dict[str, int] = field(default_factory=dict)
    universo: int = 0
    bruto: dict[str, int] = field(default_factory=dict)
    existe: bool = True

    @property
    def pendente(self) -> bool:
        return self.numero is None


@dataclass(frozen=True)
class Veredito:
    medida: Medida
    estado: str
    numero: int | None
    piso: Piso
    censo: Censo
    queixas: tuple[str, ...] = ()
    entrou: tuple[str, ...] = ()

    @property
    def passa(self) -> bool:
        """Passa a execução. VERDE e PENDENTE passam; PENDENTE **não é verde**."""
        return self.estado in (VERDE, ESTADO_PENDENTE)


class Catraca:
    """O motor. Uma instância por caderno."""

    def __init__(self, caderno: Path, medidas: Sequence[Medida], raiz: Path) -> None:
        self.caderno = Path(caderno)
        self.medidas = list(medidas)
        self.raiz = Path(raiz)
        nomes = [m.nome for m in self.medidas]
        if len(set(nomes)) != len(nomes):
            raise CatracaTorta(f"duas medidas com o mesmo nome: {nomes}")

    # -- o caderno ---------------------------------------------------------
    def _ler_caderno(self) -> dict:
        """Lê o caderno do DISCO, toda vez. Nunca de um cache em memória.

        Reler é o que impede a tautologia: se o objeto guardasse o piso da
        primeira leitura e alguém gravasse no meio, a comparação seguinte
        mediria a própria escrita.
        """
        if not self.caderno.exists():
            return {}
        return json.loads(self.caderno.read_text(encoding="utf-8"))

    def ler_piso(self, nome: str) -> Piso:
        """O piso gravado, ou um :class:`Piso` com ``existe=False``."""
        bruto = self._ler_caderno().get("medidas", {}).get(nome)
        if bruto is None:
            return Piso(numero=None, data="", razao="", existe=False)
        valor = bruto.get("piso")
        if valor == PENDENTE:
            numero: int | None = None
        elif isinstance(valor, bool) or not isinstance(valor, int):
            raise CatracaTorta(
                f"piso de «{nome}» não é inteiro nem {PENDENTE}: {valor!r}. "
                "Piso que o motor não entende viraria zero, e zero passa."
            )
        else:
            numero = valor
        razao = str(bruto.get("razao", "")).strip()
        if numero is None and not razao:
            raise CatracaTorta(
                f"«{nome}» está {PENDENTE} e SEM RAZÃO escrita. Pendência sem "
                "razão é portão desligado com aparência de decisão."
            )
        return Piso(
            numero=numero,
            data=str(bruto.get("data", "")),
            razao=razao,
            por_item=dict(bruto.get("por_item", {})),
            universo=int(bruto.get("universo", 0)),
            bruto=dict(bruto.get("bruto", {})),
        )

    # -- medir -------------------------------------------------------------
    def _medida(self, nome: str) -> Medida:
        for m in self.medidas:
            if m.nome == nome:
                return m
        raise CatracaTorta(f"medida desconhecida: {nome}")

    def medir(self, nome: str) -> Censo:
        """Roda o censo da medida contra :attr:`raiz`."""
        return self._medida(nome).censo(self.raiz)

    # -- comparar ----------------------------------------------------------
    def comparar(self, apenas: Sequence[str] | None = None) -> list[Veredito]:
        """O ato que o portão chama. **Lê o disco, mede, e não grava nada.**"""
        vereditos: list[Veredito] = []
        for medida in self.medidas:
            if apenas and medida.nome not in apenas:
                continue
            vereditos.append(self._comparar_uma(medida))
        return vereditos

    def _comparar_uma(self, medida: Medida) -> Veredito:
        piso = self.ler_piso(medida.nome)
        censo = medida.censo(self.raiz)

        # -- a mordida do vazio, e ela vem ANTES de qualquer comparação -----
        if censo.universo <= 0:
            return Veredito(
                medida,
                IMPOSSIVEL,
                censo.numero,
                piso,
                censo,
                queixas=(
                    f"universo VAZIO: o censo de «{medida.nome}» não encontrou "
                    "nada para varrer. Zero de um universo de zero não é uma "
                    "medida — é não ter olhado, e lê-se como verde. "
                    "Confira se a pasta que esta medida lê ainda está onde ela "
                    "pensa que está.",
                ),
            )
        if medida.conferir_universo is not None:
            queixa = medida.conferir_universo(self.raiz, censo)
            if queixa:
                return Veredito(
                    medida, IMPOSSIVEL, censo.numero, piso, censo, queixas=(queixa,)
                )

        # -- a pendência, nos dois sentidos --------------------------------
        if censo.indisponivel is not None and not piso.pendente and piso.existe:
            return Veredito(
                medida,
                VERMELHO,
                None,
                piso,
                censo,
                queixas=(
                    f"«{medida.nome}» tem piso NUMÉRICO ({piso.numero}) e a "
                    f"medida parou de poder medir: {censo.indisponivel}. "
                    "Piso sobre o que não se mede é piso falso — ou o dado "
                    f"volta, ou o piso vira {PENDENTE} com a razão escrita.",
                ),
            )
        if censo.indisponivel is not None:
            return Veredito(
                medida,
                ESTADO_PENDENTE,
                None,
                piso,
                censo,
                queixas=(censo.indisponivel,),
            )
        if piso.pendente and piso.existe:
            # A medida ACORDOU. O motor não espera alguém reparar.
            return Veredito(
                medida,
                VERMELHO,
                censo.numero,
                piso,
                censo,
                queixas=(
                    f"«{medida.nome}» estava {PENDENTE} e PASSOU A MEDIR: o "
                    f"censo de hoje dá {censo.numero} {medida.unidade}. "
                    "A razão da pendência caiu. Grave o piso com "
                    f"`--aceitar {medida.nome}` e escreva a razão nova.",
                ),
            )
        if not piso.existe:
            return Veredito(
                medida,
                SEM_PISO,
                censo.numero,
                piso,
                censo,
                queixas=(
                    f"«{medida.nome}» não tem piso no caderno "
                    f"({self.caderno.name}). Catraca sem piso não trava nada. "
                    f"Grave com `--aceitar {medida.nome}`.",
                ),
            )

        assert censo.numero is not None and piso.numero is not None
        if censo.numero <= piso.numero:
            return Veredito(medida, VERDE, censo.numero, piso, censo)

        entrou = self._o_que_entrou(medida, piso, censo)
        return Veredito(
            medida,
            VERMELHO,
            censo.numero,
            piso,
            censo,
            queixas=(
                f"«{medida.nome}» SUBIU: {piso.numero} -> {censo.numero} "
                f"{medida.unidade} (+{censo.numero - piso.numero}). "
                f"O piso é de {piso.data}.",
            ),
            entrou=entrou,
        )

    @staticmethod
    def _o_que_entrou(medida: Medida, piso: Piso, censo: Censo) -> tuple[str, ...]:
        """O nome do que subiu, nunca só o número.

        Um número vermelho sem o nome faz a pessoa procurar, e procurar é o que
        desliga portão.
        """
        linhas: list[str] = []
        ja_nomeados: set[str] = set()
        for chave, valor in sorted(censo.por_item.items()):
            antes = piso.por_item.get(chave)
            if antes is None:
                linhas.append(f"{chave}: NOVO, {valor} {medida.unidade}")
                ja_nomeados.add(chave)
            elif valor > antes:
                linhas.append(f"{chave}: {antes} -> {valor} (+{valor - antes})")
                ja_nomeados.add(chave)
        # `nomes` é para a medida que sabe nomear o item sem tê-lo no
        # `por_item`. Repetir o que a linha acima já disse faz a pessoa ler
        # duas vezes a mesma queixa e duvidar da contagem.
        linhas.extend(nome for nome in censo.nomes if nome not in ja_nomeados)
        return tuple(linhas)

    # -- gravar ------------------------------------------------------------
    def aceitar(self, nomes: Sequence[str] | None = None, razao: str = "") -> list[str]:
        """Desce o piso até o número de hoje. **Só desce.**

        Subir é ``forcar_piso``, que exige razão escrita. Se ``aceitar``
        também subisse, a catraca seria um botão de silenciar com nome bonito.
        """
        caderno = self._ler_caderno()
        caderno.setdefault("medidas", {})
        mexidas: list[str] = []
        hoje = date.today().isoformat()
        for medida in self.medidas:
            if nomes and medida.nome not in nomes:
                continue
            censo = medida.censo(self.raiz)
            if censo.universo <= 0:
                raise CatracaTorta(
                    f"recuso gravar piso de «{medida.nome}» sobre universo "
                    "vazio: seria gravar o silêncio como fato."
                )
            piso = self.ler_piso(medida.nome)
            registro = caderno["medidas"].setdefault(medida.nome, {})
            if censo.indisponivel is not None:
                # A RAZÃO DA PENDÊNCIA É A DA MEDIDA, não a de quem grava. Ela
                # é medida do código — some sozinha no dia em que a condição
                # cair —, e deixar alguém escrevê-la à mão faria a pendência
                # sobreviver ao motivo dela.
                registro["piso"] = PENDENTE
                registro["razao"] = censo.indisponivel
                registro["bruto"] = dict(censo.bruto)
                if razao:
                    registro["nota_de_quem_gravou"] = razao
            else:
                assert censo.numero is not None
                if piso.existe and piso.numero is not None and censo.numero > piso.numero:
                    raise CatracaTorta(
                        f"«{medida.nome}» está ACIMA do piso "
                        f"({piso.numero} -> {censo.numero}). `--aceitar` só "
                        "desce. Para subir, `--forcar-piso` com a razão."
                    )
                registro["piso"] = censo.numero
                registro["razao"] = razao or registro.get("razao", "") or (
                    "piso descido pelo censo do dia"
                )
                registro.pop("bruto", None)
            registro["data"] = hoje
            registro["o_que_conta"] = medida.o_que_conta
            registro["unidade"] = medida.unidade
            registro["universo"] = censo.universo
            registro["por_item"] = dict(censo.por_item)
            if censo.nota:
                registro["nota"] = censo.nota
            mexidas.append(medida.nome)
        self._gravar(caderno)
        return mexidas

    def forcar_piso(self, nome: str, razao: str) -> str:
        """Sobe o piso, com razão e data no caderno — e no diff de quem revisa."""
        razao = razao.strip()
        if not razao:
            raise CatracaTorta(
                "`--forcar-piso` sem razão escrita. Subir piso sem razão é a "
                "catraca girando para trás em silêncio."
            )
        medida = self._medida(nome)
        censo = medida.censo(self.raiz)
        if censo.universo <= 0:
            raise CatracaTorta(
                f"recuso subir o piso de «{nome}» sobre universo vazio."
            )
        if censo.numero is None:
            raise CatracaTorta(
                f"«{nome}» não pode medir agora ({censo.indisponivel}); não há "
                "piso a subir."
            )
        piso = self.ler_piso(nome)
        caderno = self._ler_caderno()
        caderno.setdefault("medidas", {})
        registro = caderno["medidas"].setdefault(nome, {})
        subidas = list(registro.get("subidas", []))
        subidas.append(
            {
                "data": date.today().isoformat(),
                "de": piso.numero if piso.existe else None,
                "para": censo.numero,
                "razao": razao,
            }
        )
        registro.update(
            {
                "piso": censo.numero,
                "data": date.today().isoformat(),
                "razao": razao,
                "o_que_conta": medida.o_que_conta,
                "unidade": medida.unidade,
                "universo": censo.universo,
                "por_item": dict(censo.por_item),
                "subidas": subidas,
            }
        )
        registro.pop("bruto", None)
        self._gravar(caderno)
        return f"{piso.numero if piso.existe else '(sem piso)'} -> {censo.numero}"

    def _gravar(self, caderno: dict) -> None:
        caderno.setdefault(
            "_LEIA",
            "O PISO DAS CATRACAS. Não se edita à mão: "
            "`--aceitar` desce, `--forcar-piso «razão»` sobe com razão e data.",
        )
        self.caderno.parent.mkdir(parents=True, exist_ok=True)
        self.caderno.write_text(
            json.dumps(caderno, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# A linha de comando que toda catraca ganha de graça
# ---------------------------------------------------------------------------
def montar_argumentos(descricao: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=descricao)
    p.add_argument(
        "--aceitar",
        nargs="*",
        metavar="MEDIDA",
        help="desce o piso até o censo de hoje (sem nome: todas as medidas)",
    )
    p.add_argument(
        "--forcar-piso",
        nargs=2,
        metavar=("MEDIDA", "RAZAO"),
        help="sobe o piso de uma medida, com a razão gravada no caderno",
    )
    p.add_argument("--razao", default="", help="a razão a gravar junto do --aceitar")
    p.add_argument(
        "--raiz",
        default=None,
        help="a árvore a medir (padrão: a do próprio script). "
        "É por aqui que a mordida do vazio aponta para uma pasta vazia.",
    )
    p.add_argument("--json", action="store_true", help="o relato em JSON")
    return p


def relatar(vereditos: Sequence[Veredito], titulo: str) -> int:
    """Imprime o relato e devolve o rc. VERDE e PENDENTE passam; o resto não."""
    largura = max((len(v.medida.nome) for v in vereditos), default=10)
    print(titulo)
    for v in vereditos:
        if not v.piso.existe:
            piso: object = "(sem piso)"
        else:
            piso = PENDENTE if v.piso.pendente else v.piso.numero
        agora = "—" if v.numero is None else str(v.numero)
        print(
            f"  [{v.estado:<10}] {v.medida.nome:<{largura}}  "
            f"hoje={agora:<10} piso={piso}"
        )
    print()
    ruins = [v for v in vereditos if not v.passa]
    for v in vereditos:
        if v.estado == ESTADO_PENDENTE:
            print(f"PENDENTE — {v.medida.nome}: {' '.join(v.queixas)}")
            print(
                "  Pendente NÃO é verde: esta medida não está medindo, e o "
                "caderno diz por quê.\n"
            )
    if not ruins:
        return 0
    print(f"REPROVADO — {len(ruins)} medida(s):\n")
    for v in ruins:
        for q in v.queixas:
            print(f"  {v.medida.nome}: {q}")
        for linha in v.entrou[:40]:
            print(f"      {linha}")
        if len(v.entrou) > 40:
            print(f"      ... e mais {len(v.entrou) - 40}")
        print()
    return 1


def executar(catraca: Catraca, argumentos: argparse.Namespace, titulo: str) -> int:
    """O corpo comum de `main()` de quem usa este motor.

    A recusa do motor sai como MENSAGEM, não como traceback: quem lê o vermelho
    de um portão está tentando consertar, e uma pilha de chamadas por cima da
    frase que explica o conserto é ruído.
    """
    try:
        return _executar(catraca, argumentos, titulo)
    except CatracaTorta as erro:
        print(f"RECUSADO: {erro}", file=sys.stderr)
        return 2


def _executar(catraca: Catraca, argumentos: argparse.Namespace, titulo: str) -> int:
    if argumentos.forcar_piso:
        nome, razao = argumentos.forcar_piso
        print(f"piso de «{nome}»: {catraca.forcar_piso(nome, razao)} — {razao}")
        return 0
    if argumentos.aceitar is not None:
        mexidas = catraca.aceitar(argumentos.aceitar or None, argumentos.razao)
        print("piso gravado para: " + ", ".join(mexidas))
        return 0
    vereditos = catraca.comparar()
    if argumentos.json:
        print(
            json.dumps(
                {
                    v.medida.nome: {
                        "estado": v.estado,
                        "hoje": v.numero,
                        "piso": PENDENTE if v.piso.pendente else v.piso.numero,
                        "universo": v.censo.universo,
                        "queixas": list(v.queixas),
                        "entrou": list(v.entrou),
                    }
                    for v in vereditos
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if all(v.passa for v in vereditos) else 1
    return relatar(vereditos, titulo)
