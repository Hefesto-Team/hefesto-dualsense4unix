#!/usr/bin/env python3
"""eliminacao.py — a lógica de eliminação de suspeitos, feature por feature."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENSAIOS = RAIZ / "docs" / "data" / "ensaios.csv"

CULPADO = "e-a-causa"
INOCENTE = "nao-e-a-causa"
INCONCLUSIVO = "inconclusivo"
CONFUSO = "confuso"
NUNCA = "nunca-investigado"


@dataclass
class Podavel:
    """Um suspeito INOCENTADO: mexe-se nele e o resultado não muda."""
    suspeito: str
    ensaios: int
    resultado: str = ""
    codigo_ref: str = ""


@dataclass
class Julgamento:
    suspeito: str
    veredicto: str
    com: list[str] = field(default_factory=list)
    sem: list[str] = field(default_factory=list)
    proximo_ensaio: str = ""
    ensaios: int = 0

    @property
    def conclusivo(self) -> bool:
        return self.veredicto in (CULPADO, INOCENTE)


def _sim(v: str) -> bool:
    return v.strip().lower() in ("sim", "s", "1", "true", "yes")


def julga(linhas_de_ensaio: list[dict]) -> Julgamento:
    """Julga UM suspeito a partir dos ensaios dele."""
    if not linhas_de_ensaio:
        return Julgamento("", NUNCA, proximo_ensaio="qualquer ensaio — não há nenhum")

    susp = linhas_de_ensaio[0]["suspeito"]
    com = [e["resultado"].strip() for e in linhas_de_ensaio if _sim(e["presente"])]
    sem = [e["resultado"].strip() for e in linhas_de_ensaio if not _sim(e["presente"])]
    j = Julgamento(susp, INCONCLUSIVO, com, sem, ensaios=len(linhas_de_ensaio))

    if len(set(com)) > 1 or len(set(sem)) > 1:
        j.veredicto = CONFUSO
        j.proximo_ensaio = (
            "o mesmo lado deu resultados diferentes — há variável não isolada; "
            "repita fixando tudo o mais"
        )
        return j

    if com and not sem:
        j.proximo_ensaio = f"um ensaio SEM o suspeito ({len(com)} ensaios só COM)"
        return j
    if sem and not com:
        j.proximo_ensaio = f"um ensaio COM o suspeito ({len(sem)} ensaios só SEM)"
        return j

    j.veredicto = CULPADO if com[0] != sem[0] else INOCENTE
    j.proximo_ensaio = ""
    return j


def carrega(caminho: Path = ENSAIOS) -> dict[str, list[dict]]:
    if not caminho.exists():
        return {}
    with open(caminho, encoding="utf-8", newline="") as fh:
        tudo = list(csv.DictReader(fh))
    por_linha: dict[str, list[dict]] = defaultdict(list)
    for e in tudo:
        por_linha[e["linha_id"]].append(e)
    return dict(por_linha)


LADOS = ("cabo", "radio")


def sustentam_a_ponte(ensaios: list[dict], ponte: str) -> list[dict]:
    """Dos `ensaios`, os que sustentam uma afirmação sobre `ponte`.

    A REGRA, escrita por extenso porque ela é assimétrica de propósito
    (ENSAIO-QUE-NAO-DIZ-A-PONTE-01, 20/08/2026):

    - **ensaio de `ponte` VAZIA sustenta afirmação de QUALQUER ponte.** Vazio
      quer dizer "não declarou", e os 177 ensaios do caderno nasceram assim, sem
      o campo existir. Recusá-los reprovaria hoje toda célula de grau forte que
      passa — e reprovar afirmação VERDADEIRA é o erro que esta casa já pagou
      caro em 12/08 e em 13/08.
    - **ensaio COM `ponte` sustenta só a DO USUÁRIO.** Quem declarou por onde mediu
      disse também por onde NÃO mediu: um ensaio pela máscara Xbox não fala pelo
      giroscópio, que só existe pela nossa máscara DualSense.

    Note que "vazio sustenta qualquer ponte" NÃO é o mesmo que "vazio serve para
    tudo": é a leitura mais generosa possível de um ensaio que não declarou, e
    ela vale só enquanto ninguém declara. Quem quiser exigir declaração explícita
    o faz na sua própria regra, como o portão faz com os degraus de ENTRADA.

    `ponte` vazia aqui quer dizer "a afirmação também não declarou ponte", e aí
    não há o que discriminar: devolve tudo.
    """
    alvo = ponte.strip()
    if not alvo:
        return list(ensaios)
    return [e for e in ensaios if (e.get("ponte") or "").strip() in ("", alvo)]


def carrega_por_lado(
    caminho: Path = ENSAIOS, ponte: str = "",
) -> dict[tuple[str, str], list[dict]]:
    """Como `carrega`, mas separando o cabo do rádio — e, se pedirem, a ponte."""
    if not caminho.exists():
        return {}
    with open(caminho, encoding="utf-8", newline="") as fh:
        tudo = list(csv.DictReader(fh))
    por_lado: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for e in tudo:
        por_lado[(e["linha_id"], (e.get("transporte") or "").strip())].append(e)
    if not ponte.strip():
        return dict(por_lado)
    return {
        chave: sustentados
        for chave, ensaios in por_lado.items()
        if (sustentados := sustentam_a_ponte(ensaios, ponte))
    }


def julga_linha(ensaios: list[dict]) -> list[Julgamento]:
    """Julga TODOS os suspeitos de uma linha do mapa, do mais conclusivo ao menos."""
    por_susp: dict[str, list[dict]] = defaultdict(list)
    for e in ensaios:
        por_susp[e["suspeito"]].append(e)
    js = [julga(v) for v in por_susp.values()]
    ordem = {CULPADO: 0, CONFUSO: 1, INCONCLUSIVO: 2, INOCENTE: 3, NUNCA: 4}
    return sorted(js, key=lambda j: (ordem.get(j.veredicto, 9), -j.ensaios))


def podaveis(ensaios: list[dict]) -> list[Podavel]:
    """Os suspeitos que se pode PARAR de acionar, com o preço já provado."""
    fora = []
    for j in julga_linha(ensaios):
        if j.veredicto != INOCENTE:
            continue
        ref = next((e.get("codigo_ref", "") for e in ensaios
                    if e["suspeito"] == j.suspeito and e.get("codigo_ref")), "")
        fora.append(Podavel(j.suspeito, j.ensaios, (j.com or [""])[0], ref))
    return fora


def estado_da_linha(ensaios: list[dict]) -> tuple[str, str]:
    """(estado, o que fazer agora) para uma linha do mapa."""
    if not ensaios:
        return NUNCA, "ninguém ensaiou esta linha — nem um suspeito foi levantado"
    js = julga_linha(ensaios)
    culpados = [j for j in js if j.veredicto == CULPADO]
    if culpados:
        poda = podaveis(ensaios)
        extra = (f" · {len(poda)} suspeito(s) inocentado(s) — candidatos a poda"
                 if poda else "")
        return CULPADO, f"causa isolada: {culpados[0].suspeito}{extra}"
    confusos = [j for j in js if j.veredicto == CONFUSO]
    if confusos:
        return CONFUSO, confusos[0].proximo_ensaio
    abertos = [j for j in js if j.veredicto == INCONCLUSIVO]
    if abertos:
        return INCONCLUSIVO, f"{abertos[0].suspeito} — falta {abertos[0].proximo_ensaio}"
    return INOCENTE, "nenhum dos suspeitos levantados é a causa — falta suspeito novo"


if __name__ == "__main__":
    por_lado = carrega_por_lado()
    if not por_lado:
        raise SystemExit(f"sem ensaios em {ENSAIOS}")
    for (linha_id, lado), ens in sorted(por_lado.items()):
        estado, agora = estado_da_linha(ens)
        print(f"\n{linha_id} [{lado or 'sem lado'}]\n  estado: {estado.upper()} — {agora}")
        for j in julga_linha(ens):
            marca = {CULPADO: "!!", CONFUSO: "??", INCONCLUSIVO: "..",
                     INOCENTE: "ok", NUNCA: "  "}[j.veredicto]
            print(f"   {marca} {j.suspeito[:72]}")
            print(f"      {j.ensaios} ensaio(s) · com={j.com or '—'} sem={j.sem or '—'}")
            if j.proximo_ensaio:
                print(f"      FALTA: {j.proximo_ensaio}")
