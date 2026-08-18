#!/usr/bin/env python3
"""eliminacao.py — a lógica de eliminação de suspeitos, feature por feature.

O molde é o estudo LIGHTBAR-BT-CULPADO-01 (03/08/2026). Ele levou dezesseis
dias, e o que fechou a conta foi UM ensaio: o sexto, o único com o suspeito
AUSENTE. Seis eventos com o `0x08` presente e a barra travada não provam nada
sozinhos — poderiam estar todos sendo causados por outra coisa. Foi o evento em
que o report NÃO saiu, e a barra obedeceu, que transformou correlação em causa.

Daí a regra que este módulo implementa: um suspeito só é julgado quando existe
ensaio dos DOIS lados. Enquanto só houver de um lado, o veredicto é
INCONCLUSIVO e o instrumento diz QUAL ensaio falta — que é a pergunta que
ninguém tinha para responder durante aqueles dezesseis dias.

O controle negativo do mesmo estudo (o `0x08` fora da janela, que não trava)
entra como suspeito PRÓPRIO, não como ruído: "0x08 dentro da janela" e "0x08
fora da janela" são hipóteses diferentes, e separá-las é o que isola a janela
como a variável de verdade.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENSAIOS = RAIZ / "docs" / "data" / "ensaios.csv"

#: Vereditos possíveis para um suspeito, do mais conclusivo ao mais aberto.
#:
#: O vocabulário é "é a causa"/"não é a causa", e não "culpado"/"inocente",
#: porque o mesmo instrumento serve para os dois sentidos: caçar o report que
#: TRAVA a lightbar e confirmar o byte que FAZ o motor girar. Chamar de culpado
#: um mecanismo que funciona confunde na hora de ler o mapa — e foi o que
#: aconteceu no primeiro ensaio do rumble, em 10/08.
CULPADO = "e-a-causa"         # ensaios dos dois lados, e o resultado VIRA
INOCENTE = "nao-e-a-causa"    # ensaios dos dois lados, e o resultado NÃO muda
INCONCLUSIVO = "inconclusivo"  # só um lado — falta o ensaio que discrimina
CONFUSO = "confuso"           # o mesmo lado deu resultados diferentes
NUNCA = "nunca-investigado"   # nenhum ensaio


@dataclass
class Podavel:
    """Um suspeito INOCENTADO: mexe-se nele e o resultado não muda.

    É a metade esquecida da eliminação, e no estudo da lightbar foi a que deu
    mais lucro. Ela contou assim: "de 5 canais, um deles é o que realmente
    impactava; após isso passamos a usar somente ele, e deixamos o projeto
    menos complexo". Os outros quatro continuavam sendo escritos a cada report
    — custo, risco de disputa e superfície de defeito — sem efeito nenhum.

    Um culpado isolado responde "por onde eu aciono". Os inocentados respondem
    "o que eu posso PARAR de fazer", e essa é a pergunta que encolhe o código.
    """
    suspeito: str
    ensaios: int
    resultado: str = ""       # o mesmo dos dois lados: por isso é podável
    codigo_ref: str = ""      # onde ele é acionado hoje, se se sabe


@dataclass
class Julgamento:
    suspeito: str
    veredicto: str
    com: list[str] = field(default_factory=list)      # resultados com o suspeito
    sem: list[str] = field(default_factory=list)      # resultados sem o suspeito
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

    # Um lado que se contradiz derruba o julgamento inteiro: alguma variável
    # que ninguém isolou está mandando mais que o suspeito.
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


#: Os dois lados do mapa v2. O ensaio guarda em qual deles foi feito, porque
#: `linha_id` sozinho já não distingue cabo de rádio: no v2 a feature inteira é
#: UMA linha.
LADOS = ("cabo", "radio")


def carrega_por_lado(caminho: Path = ENSAIOS) -> dict[tuple[str, str], list[dict]]:
    """Como `carrega`, mas separando o cabo do rádio.

    Isto NÃO é refinamento: é o que impede a migração para o v2 de apagar o
    estudo da lightbar. Os sete ensaios por rádio e o do cabo levantam o MESMO
    suspeito — "0x08 na janela de 3,4 s" — e dão resultados opostos, porque o
    cabo não tem janela nem máquina de estados. Num balde só, `julga()` veria um
    lado se contradizendo e devolveria CONFUSO, jogando fora dezesseis dias de
    isolamento. Separados, o rádio continua com o culpado isolado e o cabo
    continua explicando o que JÁ funcionava.
    """
    if not caminho.exists():
        return {}
    with open(caminho, encoding="utf-8", newline="") as fh:
        tudo = list(csv.DictReader(fh))
    por_lado: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for e in tudo:
        por_lado[(e["linha_id"], (e.get("transporte") or "").strip())].append(e)
    return dict(por_lado)


def julga_linha(ensaios: list[dict]) -> list[Julgamento]:
    """Julga TODOS os suspeitos de uma linha do mapa, do mais conclusivo ao menos."""
    por_susp: dict[str, list[dict]] = defaultdict(list)
    for e in ensaios:
        por_susp[e["suspeito"]].append(e)
    js = [julga(v) for v in por_susp.values()]
    ordem = {CULPADO: 0, CONFUSO: 1, INCONCLUSIVO: 2, INOCENTE: 3, NUNCA: 4}
    return sorted(js, key=lambda j: (ordem.get(j.veredicto, 9), -j.ensaios))


def podaveis(ensaios: list[dict]) -> list[Podavel]:
    """Os suspeitos que se pode PARAR de acionar, com o preço já provado.

    Só entra aqui quem foi ensaiado dos DOIS lados e não mudou o resultado.
    Suspeito inconclusivo não é podável: "não sei se faz efeito" e "provei que
    não faz efeito" são coisas diferentes, e confundir as duas é como arrancar
    a cura de alguém achando que era enfeite.
    """
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
