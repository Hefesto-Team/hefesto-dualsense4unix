#!/usr/bin/env python3
"""O tempo da casa só desce: a suíte, o portão rápido e o completo têm piso de segundos.

Três medidas, lidas dos registros que o fecho e o rápido já deixam em ``$CASA``:

* ``suite-pytest-s``: a soma do tempo de pytest das 24 partes (``fecho/suite/parte-NN.txt``) de UMA
  corrida: a marca de cada parte (a árvore, o número de arquivos e a partição) tem de bater, e o fecho
  que reaproveitou o recibo de uma parte não alimenta o piso;
* ``rapido-mediana-s``: a mediana de parede das últimas corridas do rápido (``rapido-*.log``);
* ``completo-parede-s``: a parede do último ``portoes.sh`` completo (``fecho/portoes-*.out``).

Tempo é ruído: cada medida leva uma ``folga`` em porcento no caderno
(``docs/data/tempos-da-casa.json``). Dentro dela nada muda. Acima dela reprova, e só passa com
``Tempo: <medida> <razão>`` na mensagem de um commit da faixa da leva (a razão é obrigatória).
Abaixo dela, o piso desce. O piso mora no motor de ``scripts/catraca.py``.

``--fechar`` é o passo do fecho: paga a subida com o trailer, desce o piso que desceu além da folga
e AVISA (rc 0) a medida que ficou sem dado; ``--fechar --conferir`` diz o que faria, sem gravar.
"""

from __future__ import annotations

import os
import re
import statistics
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catraca import (
    ESTADO_PENDENTE,
    SEM_PISO,
    VERDE,
    VERMELHO,
    Catraca,
    CatracaTorta,
    Censo,
    Medida,
    Veredito,
    executar,
    montar_argumentos,
)

CADERNO = Path("docs/data/tempos-da-casa.json")
SUITE = "suite-pytest-s"
RAPIDO = "rapido-mediana-s"
COMPLETO = "completo-parede-s"
PARTES = 24
CORRIDAS_DO_RAPIDO = 9
MINIMO_DE_CORRIDAS = 5

_PARTE = re.compile(r"^\s*parte-(\d+) \(\d+ arq\): .* in ([\d.]+)s")
_PROCESSO_PROPRIO = re.compile(r"^\s+\S+, em processo próprio: .* in ([\d.]+)s")
_MARCA = re.compile(r"^\s*corrida árvore=(\S+) arquivos=(\d+) partição=(\S+)\s*$", re.M)
_CABECALHO = re.compile(r"^suíte — (\d+) arquivos em (\d+) partes", re.M)
REAPROVEITADAS = "reaproveitadas.txt"
_PAREDE = re.compile(r"^tempo: (\d+) s de parede", re.M)
_CAMADAS = re.compile(r"^\s*camadas .*\bcompleto\b", re.M)
_TRAILER = re.compile(r"^Tempo:[ \t]+(\S+)[ \t]+(\S.*?)[ \t]*$", re.M)


def _sem_casa(o_que: str) -> Censo:
    return Censo(numero=None, universo=1, indisponivel=o_que)


def _corrida(texto: str) -> str:
    """A marca da corrida que a parte traz; sem ela, o cabeçalho (que já separa as partições)."""
    if m := _MARCA.search(texto):
        return f"árvore {m[1]}, {m[2]} arquivos, partição {m[3]}"
    if m := _CABECALHO.search(texto):
        return f"{m[1]} arquivos em {m[2]} partes, sem marca"
    return "sem marca nem cabeçalho"


def censo_da_suite(casa: Path | None) -> Censo:
    """Soma o pytest das 24 partes de UMA corrida; parte, linha ou marca que falta é indisponível.

    O fecho guarda o recibo da parte verde e só reroda a vermelha, e a partição muda com o número de
    arquivos: em 23/10 as 24 partes vinham de quatro corridas (O-TEMPO-DA-SUITE-SO-SOMA-UMA-CORRIDA-01).
    """
    if casa is None:
        return _sem_casa("a casa não foi informada (`--casa` ou $CASA)")
    pasta = casa / "fecho" / "suite"
    por_parte: dict[str, float] = {}
    corridas: dict[str, list[str]] = {}
    for n in range(PARTES):
        arquivo = pasta / f"parte-{n:02d}.txt"
        if not arquivo.is_file():
            return Censo(numero=None, universo=PARTES,
                         indisponivel=f"falta {arquivo.name} em {pasta}")
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        corridas.setdefault(_corrida(texto), []).append(f"{n:02d}")
        soma = 0.0
        achou = False
        for linha in texto.splitlines():
            m = _PARTE.match(linha) or _PROCESSO_PROPRIO.match(linha)
            if m:
                achou = True
                soma += float(m.groups()[-1])
        if not achou:
            return Censo(numero=None, universo=PARTES,
                         indisponivel=f"{arquivo.name} não traz a linha de sumário do pytest")
        por_parte[f"parte-{n:02d}"] = soma
    if len(corridas) > 1:
        cada = "; ".join(f"{marca} (partes {' '.join(partes)})" for marca, partes in corridas.items())
        return Censo(numero=None, universo=PARTES,
                     indisponivel=f"partes de {len(corridas)} corridas em {pasta}: {cada}")
    marca = next(iter(corridas))
    if not marca.startswith("árvore "):
        return Censo(numero=None, universo=PARTES,
                     indisponivel=f"as partes em {pasta} não trazem a marca da corrida ({marca})")
    reaproveitadas = pasta / REAPROVEITADAS
    if reaproveitadas.is_file() and reaproveitadas.read_text(encoding="utf-8").split(":")[-1].split():
        return Censo(numero=None, universo=PARTES,
                     indisponivel=(f"o fecho reaproveitou o recibo de partes de antes "
                                   f"({reaproveitadas.read_text(encoding='utf-8').strip()}): "
                                   "a soma junta horas diferentes"))
    return Censo(numero=round(sum(por_parte.values())), universo=PARTES,
                 por_item={k: round(v) for k, v in por_parte.items()},
                 nota=f"segundos de pytest das {PARTES} partes de uma corrida da suíte ({marca})")


def _mais_novos(arquivos: list[Path]) -> list[Path]:
    return sorted(arquivos, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)


def censo_do_rapido(casa: Path | None) -> Censo:
    """A mediana de parede das últimas corridas do rápido: uma corrida lenta não vira piso."""
    if casa is None:
        return _sem_casa("a casa não foi informada (`--casa` ou $CASA)")
    tempos: dict[str, int] = {}
    for log in _mais_novos(list(casa.glob("rapido-*.log"))):
        achou = _PAREDE.findall(log.read_text(encoding="utf-8", errors="replace"))
        if achou:
            tempos[log.name] = int(achou[-1])
        if len(tempos) == CORRIDAS_DO_RAPIDO:
            break
    if len(tempos) < MINIMO_DE_CORRIDAS:
        return Censo(numero=None, universo=max(len(tempos), 1),
                     indisponivel=(f"só {len(tempos)} corrida(s) do rápido com tempo em {casa} "
                                   f"(mínimo {MINIMO_DE_CORRIDAS})"))
    return Censo(numero=round(statistics.median(tempos.values())), universo=len(tempos),
                 por_item=tempos, nota=f"mediana da parede das últimas {len(tempos)} corridas do rápido")


def censo_do_completo(casa: Path | None) -> Censo:
    """A parede do último ``portoes.sh`` completo do fecho (o que traz a camada ``completo``)."""
    if casa is None:
        return _sem_casa("a casa não foi informada (`--casa` ou $CASA)")
    for saida in _mais_novos(list((casa / "fecho").glob("portoes-*.out"))):
        texto = saida.read_text(encoding="utf-8", errors="replace")
        achou = _PAREDE.findall(texto)
        if _CAMADAS.search(texto) and achou:
            return Censo(numero=int(achou[-1]), universo=1, por_item={saida.name: int(achou[-1])},
                         nota="parede do último portoes.sh completo do fecho")
    return Censo(numero=None, universo=1,
                 indisponivel=f"nenhum portoes-*.out completo com a linha `tempo:` em {casa}/fecho")


def medidas_da(casa: Path | None) -> tuple[Medida, ...]:
    def com(f: Callable[[Path | None], Censo]) -> Callable[[Path], Censo]:
        return lambda _raiz: f(casa)

    return (
        Medida(SUITE, "segundos de pytest da suíte inteira (24 partes)", com(censo_da_suite), "s"),
        Medida(RAPIDO, "mediana, em segundos, da parede do portão rápido", com(censo_do_rapido), "s"),
        Medida(COMPLETO, "segundos de parede do portão completo", com(censo_do_completo), "s"),
    )


class CatracaDoTempo(Catraca):
    """O motor, com a folga: tempo é ruído, e o piso só se mexe fora dela."""

    def folga(self, nome: str) -> int:
        bruto = self._ler_caderno().get("medidas", {}).get(nome, {})
        valor = bruto.get("folga")
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            raise CatracaTorta(
                f"«{nome}» não tem `folga` (porcento inteiro) no caderno: sem ela a catraca do tempo "
                "reprovaria o ruído ou deixaria passar tudo.")
        return valor

    def _comparar_uma(self, medida: Medida) -> Veredito:
        v = super()._comparar_uma(medida)
        if v.estado not in (VERDE, VERMELHO) or v.numero is None or v.piso.numero is None:
            return v
        folga = self.folga(medida.nome)
        if v.numero * 100 <= v.piso.numero * (100 + folga):
            return Veredito(medida, VERDE, v.numero, v.piso, v.censo)
        return Veredito(
            medida, VERMELHO, v.numero, v.piso, v.censo,
            queixas=(f"«{medida.nome}» passou da folga de {folga}%: {v.piso.numero} -> {v.numero} s "
                     f"(+{v.numero - v.piso.numero}). O piso é de {v.piso.data}. Pague com "
                     f"`Tempo: {medida.nome} <razão>` na mensagem de um commit da faixa.",),
            entrou=v.entrou)

    def desceu_alem_da_folga(self, v: Veredito) -> bool:
        if v.numero is None or v.piso.numero is None:
            return False
        return v.numero * 100 < v.piso.numero * (100 - self.folga(v.medida.nome))


def _base_da_leva(raiz: Path) -> str | None:
    base = os.environ.get("HEFESTO_BASE_DA_LEVA")
    if base:
        return base
    achado = subprocess.run(["git", "merge-base", "HEAD", "dev"], cwd=raiz, capture_output=True,
                            text=True, check=False)
    topo = subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True, text=True,
                          check=False).stdout.strip()
    if achado.returncode == 0 and achado.stdout.strip() not in ("", topo):
        return achado.stdout.strip()
    ultimo = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(CADERNO)], cwd=raiz,
                            capture_output=True, text=True, check=False)
    return ultimo.stdout.strip() or None if ultimo.returncode == 0 else None


def pagamentos_da_faixa(raiz: Path, base: str | None = None) -> dict[str, str]:
    """``{medida: razão}`` dos trailers ``Tempo:`` de ``base..HEAD``; o mais novo vale."""
    base = base or _base_da_leva(raiz)
    if not base:
        return {}
    saida = subprocess.run(["git", "log", "--reverse", "--format=%B%x00", f"{base}..HEAD"], cwd=raiz,
                           capture_output=True, text=True, check=False)
    pagos: dict[str, str] = {}
    if saida.returncode == 0:
        for mensagem in saida.stdout.split("\0"):
            for nome, razao in _TRAILER.findall(mensagem):
                pagos[nome] = razao
    return pagos


def fechar(catraca: CatracaDoTempo, raiz: Path, base: str | None, so_conferir: bool) -> tuple[int, list[str]]:
    """O passo do fecho. ``(rc, linhas)``: 0 segue, 1 reprova, e só grava sem ``so_conferir``."""
    pagos = pagamentos_da_faixa(raiz, base)
    verbo = "faria" if so_conferir else "fez"
    linhas: list[str] = []
    rc = 0
    for v in catraca.comparar():
        nome = v.medida.nome
        if v.estado == ESTADO_PENDENTE or v.numero is None:
            linhas.append(f"AVISO {nome}: sem dado hoje ({'; '.join(v.queixas) or v.censo.indisponivel}); "
                          "o piso fica onde está.")
        elif v.estado == SEM_PISO:
            linhas.append(f"REPROVADO {nome}: sem piso no caderno ({v.numero} s). "
                          f"Grave com `--aceitar {nome}`.")
            rc = 1
        elif v.estado == VERMELHO:
            if nome in pagos:
                linhas.append(f"{verbo} subir {nome}: {v.piso.numero} -> {v.numero} s, "
                              f"pago por `Tempo:` — {pagos[nome]}")
                if not so_conferir:
                    catraca.forcar_piso(nome, pagos[nome])
            else:
                linhas.append(f"REPROVADO {nome}: {v.queixas[0] if v.queixas else 'subiu'}")
                rc = 1
        elif catraca.desceu_alem_da_folga(v):
            linhas.append(f"{verbo} descer {nome}: {v.piso.numero} -> {v.numero} s")
            if not so_conferir:
                catraca.aceitar([nome], f"o tempo desceu: {v.piso.numero} -> {v.numero} s")
        else:
            linhas.append(f"{nome}: {v.numero} s, piso {v.piso.numero} s, dentro da folga")
    return rc, linhas


def main(argv: list[str] | None = None) -> int:
    p = montar_argumentos((__doc__ or "").split("\n", 1)[0])
    p.add_argument("--casa", default=os.environ.get("CASA"), help="onde moram os registros do fecho")
    p.add_argument("--base", default=None, help="a faixa dos commits do trailer `Tempo:` (base..HEAD)")
    p.add_argument("--fechar", action="store_true",
                   help="o passo do fecho: paga a subida com `Tempo:`, desce o piso, avisa o que não mediu")
    p.add_argument("--conferir", action="store_true", help="com --fechar: diz o que faria, sem gravar")
    a = p.parse_args(argv)
    raiz = Path(a.raiz) if a.raiz else RAIZ
    casa = Path(a.casa) if a.casa else None
    catraca = CatracaDoTempo(raiz / CADERNO, medidas_da(casa), raiz)
    if a.conferir and not a.fechar:
        print("RECUSADO: --conferir só vale com --fechar", file=sys.stderr)
        return 2
    if a.fechar:
        if a.aceitar is not None or a.forcar_piso:
            print("RECUSADO: --fechar não se mistura com --aceitar nem --forcar-piso", file=sys.stderr)
            return 2
        try:
            rc, linhas = fechar(catraca, raiz, a.base, a.conferir)
        except CatracaTorta as erro:
            print(f"RECUSADO: {erro}", file=sys.stderr)
            return 2
        for linha in linhas:
            print(f"  {linha}")
        return rc
    rc = executar(catraca, a, "O tempo da casa")
    if rc == 0 and a.aceitar is None and not a.forcar_piso and not a.json:
        try:
            for v in catraca.comparar():
                if catraca.desceu_alem_da_folga(v):
                    print(f"  desceu além da folga ({v.piso.numero} -> {v.numero} s): grave o piso novo "
                          f"com `{Path(sys.argv[0]).name} --casa <casa> --aceitar {v.medida.nome}`")
        except CatracaTorta as erro:
            print(f"RECUSADO: {erro}", file=sys.stderr)
            return 2
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
