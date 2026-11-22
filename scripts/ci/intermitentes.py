#!/usr/bin/env python3
"""Os intermitentes do CI: o teste que reprova em parte das pernas da mesma corrida.

Só leitura do ``gh``: baixa as corridas do ``ci.yml`` de um período, os jobs e o log de cada perna vermelha,
cruza as pernas da MESMA corrida e escreve a tabela teste x corridas x última vez.

Um teste oscila numa corrida quando reprovou numa perna e passou em outra perna que o rodou. A perna que
prova o verde do teste é a de faixa igual ou maior (``partes 00-05`` contém ``00-03``), com o passo da suíte
concluído e, se a própria perna ficou vermelha, o log lido sem o teste. Perna sem log, com processo que morreu
sem sumário, de faixa sem número (``partes janela-e-bandeja`` roda um lote) ou de faixa que não contém a do
vermelho não prova nada: o teste vermelho em todas as pernas que se sabem rodá-lo não é intermitente,
é defeito. A coluna «no mesmo SHA verde» conta as corridas em que o teste oscilou e o mesmo commit tem
outra corrida verde: é a prova mais forte (o código era o mesmo). Os SHAs com corrida verde e vermelha no
mesmo commit saem numa segunda tabela.

O que já foi baixado mora na pasta dada em ``--pasta`` (``jobs/<corrida>.json``, ``logs/job-<job>.log``, e as
corridas em ``--corridas``); ``--sem-gh`` só lê a pasta. Com ``--razoes``, cada linha da tabela leva a sprint
ou a razão que a lista conhecida dá (uma tabela em markdown cuja primeira célula é o teste entre crases e a
última é a razão); ``--exigir-razao`` sai com rc 1 se alguma linha ficar sem.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = "Hefesto-Team/hefesto-dualsense4unix"
FLUXO = "ci.yml"
LIMITE_DE_CORRIDAS = 500
PARTES = 24
SEM_RAZAO = "SEM RAZÃO"

_PERNA = re.compile(r"^(lint-test|Interface com GTK REAL)")
_FAIXA = re.compile(r"partes (\d+)-(\d+)\s*$")
_SEM_FAIXA = re.compile(r"partes \S")
_MORREU_SEM_SUMARIO = "SEM SUMÁRIO"
_VERMELHO = re.compile(r"^(?:\S+Z )?(?:FAILED|ERROR) (tests/\S+)", re.M)
_PASSOU = re.compile(r"^(?:\S+Z )?(tests/\S+) PASSED\b", re.M)
_LINHA_DA_RAZAO = re.compile(r"^\|\s*`([^`]+)`\s*\|(.*)\|\s*$")


@dataclass(frozen=True)
class Perna:
    """Uma perna da matriz do CI: o job, a faixa de partes que ele roda e o que o log dele disse."""

    nome: str
    conclusao: str
    passos: dict[str, str]
    faixa: tuple[int, int] | None
    vermelhos: frozenset[str] | None
    passou: frozenset[str] = frozenset()
    sem_sumario: bool = False

    def rodou(self, teste: str) -> bool:
        """O passo da suíte que carrega o teste chegou a rodar (verde ou vermelho)."""
        miolo = "Pytest core" if teste.startswith("tests/core/") else "Pytest unit"
        for nome, conclusao in self.passos.items():
            if (nome.startswith(miolo) or "suíte inteira" in nome) and conclusao in ("success", "failure"):
                return True
        return False

    def contem(self, outra: Perna) -> bool:
        """A faixa desta perna cobre a da outra; a faixa sem número (um lote) só é coberta pelas 24 partes."""
        if self.faixa is None:
            return False
        if outra.faixa is None:
            return self.faixa == (0, PARTES - 1)
        return self.faixa[0] <= outra.faixa[0] and outra.faixa[1] <= self.faixa[1]


@dataclass
class Corrida:
    id: str
    sha: str
    ramo: str
    data: str
    conclusao: str
    pernas: list[Perna] = field(default_factory=list)


def faixa_do_job(nome: str) -> tuple[int, int] | None:
    """``partes 04-07`` vira ``(4, 7)``; o job sem faixa roda as 24 partes; ``partes janela-e-bandeja``
    (um lote, sem número) vira ``None``."""
    if m := _FAIXA.search(nome):
        return int(m[1]), int(m[2])
    if _SEM_FAIXA.search(nome):
        return None
    return 0, PARTES - 1


def vermelhos_do_log(texto: str) -> frozenset[str]:
    """Os testes que o log do job lista como vermelhos (``FAILED``/``ERROR``), sem a mensagem."""
    return frozenset(m[1] for m in _VERMELHO.finditer(texto))


def aprovados_do_log(texto: str) -> frozenset[str]:
    """Os testes que o log (``-v``) diz terem passado; a maioria dos logs recentes não os lista."""
    return frozenset(m[1] for m in _PASSOU.finditer(texto))


def pernas_da_corrida(jobs: list[dict[str, Any]], log_do_job: Any) -> list[Perna]:
    """As pernas de teste da corrida; ``log_do_job(id)`` devolve o texto do log ou ``None``."""
    pernas: list[Perna] = []
    for j in jobs:
        nome = str(j.get("name", ""))
        if not _PERNA.match(nome) or j.get("conclusion") not in ("success", "failure"):
            continue
        passos = {str(s.get("name", "")): str(s.get("conclusion", "")) for s in j.get("steps", [])}
        texto = log_do_job(j.get("databaseId")) if j["conclusion"] == "failure" else None
        if j["conclusion"] == "success":
            vermelhos: frozenset[str] | None = frozenset()
        else:
            vermelhos = vermelhos_do_log(texto) if texto is not None else None
        pernas.append(Perna(nome, j["conclusion"], passos, faixa_do_job(nome), vermelhos,
                            aprovados_do_log(texto) if texto else frozenset(),
                            bool(texto) and _MORREU_SEM_SUMARIO in str(texto)))
    return pernas


def oscila(pernas: list[Perna], teste: str) -> bool:
    """O teste reprovou em alguma perna e passou em outra que o rodou, na mesma corrida."""
    vermelhas = [p for p in pernas if p.vermelhos is not None and teste in p.vermelhos]
    for v in vermelhas:
        for p in pernas:
            if p is v or p.vermelhos is None or teste in p.vermelhos:
                continue
            if teste in p.passou:
                return True
            if p.sem_sumario or not p.contem(v):
                continue
            if p.rodou(teste):
                return True
    return False


def funcao_do_teste(teste: str) -> str:
    """O teste sem os parâmetros: ``arq.py::nome[a-b]`` vira ``arq.py::nome``."""
    return teste.split("[", 1)[0]


@dataclass
class Linha:
    funcao: str
    oscilou: list[tuple[str, str]] = field(default_factory=list)
    vermelho_em_todas: list[tuple[str, str]] = field(default_factory=list)
    mesmo_sha_verde: int = 0
    razao: str = ""

    @property
    def ultima(self) -> str:
        todas = [d for _, d in self.oscilou] + [d for _, d in self.vermelho_em_todas]
        return max(todas) if todas else ""


def cruzar(corridas: list[Corrida]) -> list[Linha]:
    """A tabela: uma linha por função de teste que oscilou em ao menos uma corrida."""
    por_funcao: dict[str, Linha] = {}
    verdes = {c.sha for c in corridas if c.conclusao == "success"}
    sha_verde: dict[str, set[str]] = defaultdict(set)
    oscilou: dict[str, dict[str, str]] = defaultdict(dict)
    firme: dict[str, dict[str, str]] = defaultdict(dict)
    for c in corridas:
        vistos = {t for p in c.pernas if p.vermelhos for t in p.vermelhos}
        for teste in vistos:
            funcao = funcao_do_teste(teste)
            if oscila(c.pernas, teste):
                oscilou[funcao].setdefault(c.id, c.data)
                if c.sha in verdes:
                    sha_verde[funcao].add(c.id)
            else:
                firme[funcao].setdefault(c.id, c.data)
    for funcao, corridas_da_funcao in oscilou.items():
        linha = por_funcao.setdefault(funcao, Linha(funcao))
        linha.oscilou = sorted(corridas_da_funcao.items(), key=lambda x: x[1])
        linha.mesmo_sha_verde = len(sha_verde[funcao])
        linha.vermelho_em_todas = sorted(
            ((i, d) for i, d in firme.get(funcao, {}).items() if i not in corridas_da_funcao),
            key=lambda x: x[1])
    return sorted(por_funcao.values(), key=lambda ln: (-ln.mesmo_sha_verde, -len(ln.oscilou), ln.funcao))


def shas_com_verde_e_vermelho(corridas: list[Corrida]) -> list[tuple[str, list[str], list[str]]]:
    """``(sha, corridas verdes, corridas vermelhas)`` dos commits com as duas, do mais novo ao mais velho."""
    por_sha: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(lambda: {"success": [], "failure": []})
    for c in corridas:
        if c.conclusao in ("success", "failure"):
            por_sha[c.sha][c.conclusao].append((c.data, c.id))
    achados = [
        (sha, sorted(d["success"]), sorted(d["failure"]))
        for sha, d in por_sha.items() if d["success"] and d["failure"]
    ]
    achados.sort(key=lambda a: a[2][-1][0], reverse=True)
    return [(sha, [i for _, i in v], [i for _, i in r]) for sha, v, r in achados]


def razoes_da_lista(arquivo: Path) -> dict[str, str]:
    """``{teste: razão}`` da tabela em markdown: a primeira célula entre crases, a última é a razão."""
    razoes: dict[str, str] = {}
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if m := _LINHA_DA_RAZAO.match(linha):
            celulas = [c.strip() for c in m[2].split("|") if c.strip()]
            if celulas:
                razoes[m[1]] = celulas[-1]
    return razoes


def chave_casa(chave: str, funcao: str) -> bool:
    """A chave da lista nomeia o arquivo, a classe ou a função inteira: ``test_a.py`` casa
    ``tests/unit/test_a.py::test_x`` e não ``tests/unit/test_xa.py``; ``test_a.py::test_x`` não casa ``test_x2``."""
    caminho = "/" + funcao
    return caminho.endswith("/" + chave) or ("/" + chave + "::") in caminho


def aplicar_razoes(linhas: list[Linha], razoes: dict[str, str]) -> None:
    for linha in linhas:
        for chave, razao in razoes.items():
            if chave_casa(chave, linha.funcao):
                linha.razao = razao
                break
        else:
            linha.razao = SEM_RAZAO


def tabela_em_markdown(linhas: list[Linha], shas: list[tuple[str, list[str], list[str]]],
                       com_razao: bool, n_corridas: int, periodo: str) -> str:
    cab = "| teste | corridas oscilando | no mesmo SHA verde | vermelho em todas | última vez |"
    sep = "| --- | ---: | ---: | ---: | --- |"
    if com_razao:
        cab += " sprint ou razão |"
        sep += " --- |"
    saida = [f"Intermitentes do CI em {periodo}: {n_corridas} corrida(s) lidas.", "", cab, sep]
    for ln in linhas:
        linha = (f"| `{ln.funcao}` | {len(ln.oscilou)} | {ln.mesmo_sha_verde} | "
                 f"{len(ln.vermelho_em_todas)} | {ln.ultima} |")
        saida.append(linha + (f" {ln.razao} |" if com_razao else ""))
    if not linhas:
        saida.append("| (nenhum teste oscilou) | 0 | 0 | 0 | |" + (" |" if com_razao else ""))
    saida += ["", "SHAs com corrida verde e vermelha no mesmo commit:", ""]
    if shas:
        saida += ["| sha | verdes | vermelhas |", "| --- | --- | --- |"]
        saida += [f"| {sha[:9]} | {', '.join(v)} | {', '.join(r)} |" for sha, v, r in shas]
    else:
        saida.append("(nenhum)")
    return "\n".join(saida) + "\n"


def _gh(*args: str) -> str | None:
    """Só leitura do GitHub: ``gh run list|view`` e ``gh api`` de logs; ``None`` se falhar."""
    achado = subprocess.run(["gh", *args], capture_output=True, text=True, check=False, timeout=180)
    return achado.stdout if achado.returncode == 0 else None


def _ler_json(arquivo: Path) -> Any:
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def corridas_do_periodo(repo: str, desde: str, ate: str, arquivo: Path | None,
                        com_gh: bool) -> list[dict[str, Any]]:
    """As corridas do ``ci.yml`` entre as datas (``aaaa-mm-dd``), do arquivo dado ou do ``gh``."""
    brutas = _ler_json(arquivo) if arquivo is not None and arquivo.is_file() else None
    if brutas is None and com_gh:
        saida = _gh("run", "list", "-R", repo, "--workflow", FLUXO, "--limit", str(LIMITE_DE_CORRIDAS),
                    "--created", f"{desde}..{ate}", "--json",
                    "conclusion,createdAt,databaseId,event,headBranch,headSha,status")
        brutas = json.loads(saida) if saida else None
        if brutas is not None and arquivo is not None:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_text(json.dumps(brutas, indent=1) + "\n", encoding="utf-8")
    if not isinstance(brutas, list):
        return []
    return [r for r in brutas if desde <= str(r.get("createdAt", ""))[:10] <= ate]


def montar_corridas(brutas: list[dict[str, Any]], pasta: Path, repo: str, com_gh: bool) -> list[Corrida]:
    """Lê (e, com o ``gh``, baixa) os jobs e os logs das corridas vermelhas; a verde só entra no SHA."""
    (pasta / "jobs").mkdir(parents=True, exist_ok=True)
    (pasta / "logs").mkdir(parents=True, exist_ok=True)

    def log_do_job(job: Any) -> str | None:
        arquivo = pasta / "logs" / f"job-{job}.log"
        if arquivo.is_file() and arquivo.stat().st_size > 0:
            return arquivo.read_text(encoding="utf-8", errors="replace")
        if not com_gh:
            return None
        texto = _gh("api", f"repos/{repo}/actions/jobs/{job}/logs")
        if texto:
            arquivo.write_text(texto, encoding="utf-8")
        return texto or None

    corridas: list[Corrida] = []
    for r in sorted(brutas, key=lambda x: str(x.get("createdAt", ""))):
        corrida = Corrida(str(r["databaseId"]), str(r.get("headSha", "")), str(r.get("headBranch", "")),
                          str(r.get("createdAt", ""))[:10], str(r.get("conclusion", "")))
        if corrida.conclusao == "failure":
            arquivo = pasta / "jobs" / f"{corrida.id}.json"
            jobs = _ler_json(arquivo)
            if jobs is None and com_gh:
                saida = _gh("run", "view", corrida.id, "-R", repo, "--json", "jobs")
                if saida:
                    arquivo.write_text(saida, encoding="utf-8")
                    jobs = json.loads(saida)
            if isinstance(jobs, dict):
                corrida.pernas = pernas_da_corrida(jobs.get("jobs", []), log_do_job)
        corridas.append(corrida)
    return corridas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    p.add_argument("--repo", default=REPO)
    p.add_argument("--desde", required=True, help="primeiro dia (aaaa-mm-dd)")
    p.add_argument("--ate", required=True, help="último dia (aaaa-mm-dd)")
    p.add_argument("--pasta", required=True, help="onde moram (e onde vão) os jobs e os logs baixados")
    p.add_argument("--corridas", default=None, help="o json das corridas (padrão: <pasta>/corridas.json)")
    p.add_argument("--sem-gh", action="store_true", help="só lê a pasta; não chama o gh")
    p.add_argument("--razoes", default=None, help="a lista conhecida: tabela em markdown com a razão")
    p.add_argument("--exigir-razao", action="store_true", help="rc 1 se uma linha ficar sem sprint nem razão")
    p.add_argument("--saida", default=None, help="escreve a tabela neste arquivo, além de imprimir")
    a = p.parse_args(argv)
    pasta = Path(a.pasta)
    arquivo = Path(a.corridas) if a.corridas else pasta / "corridas.json"
    brutas = corridas_do_periodo(a.repo, a.desde, a.ate, arquivo, not a.sem_gh)
    if not brutas:
        print(f"RECUSADO: nenhuma corrida do {FLUXO} entre {a.desde} e {a.ate} (arquivo {arquivo})",
              file=sys.stderr)
        return 2
    corridas = montar_corridas(brutas, pasta, a.repo, not a.sem_gh)
    linhas = cruzar(corridas)
    com_razao = a.razoes is not None
    if com_razao:
        aplicar_razoes(linhas, razoes_da_lista(Path(a.razoes)))
    texto = tabela_em_markdown(linhas, shas_com_verde_e_vermelho(corridas), com_razao, len(corridas),
                               f"{a.desde} a {a.ate}")
    print(texto, end="")
    if a.saida:
        Path(a.saida).write_text(texto, encoding="utf-8")
    if a.exigir_razao and any(ln.razao == SEM_RAZAO for ln in linhas):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
