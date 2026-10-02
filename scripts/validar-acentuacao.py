#!/usr/bin/env python3
"""
Validador estrito de acentuação PT-BR para o repositório Hefesto - DualSense4Unix.

Varre arquivos de código, scripts e documentação em busca de palavras
escritas sem o acento canônico (ex.: ``funcao`` em vez de ``função``,
``acao`` em vez de ``ação``). Usado como gate de pré-commit e no CI.

Uso:
    scripts/validar-acentuacao.py --all
    scripts/validar-acentuacao.py --check-file caminho/arquivo.py
    scripts/validar-acentuacao.py --check-file arquivo1.py arquivo2.md
    scripts/validar-acentuacao.py arquivo1.py arquivo2.md
    scripts/validar-acentuacao.py --show-whitelist

Regras:
- Ignora identificadores em UPPERCASE_SNAKE (IDs de sprint, constantes).
- Em ``.md``, pula conteúdo dentro de blocos de código cercados (``` ```)
  e blocos indentados por 4+ espaços.
- Ignora qualquer linha contendo ``# noqa: acentuacao`` ou ``noqa-acento``.
- Aplica whitelist de paths (ver ``WHITELIST_PATTERNS``).

Exit code 0 se limpo, 1 se houver violações.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

A = "á"
E = "é"
I_ = "í"
O_ = "ó"
U = "ú"
AT = "ã"
OT = "õ"
AC = "â"
EC = "ê"
OC = "ô"
CC = "ç"


def _par(errada: str, correta: str) -> tuple[str, str]:
    return (errada, correta)


_PARES: list[tuple[str, str]] = [
    _par("a" + "cao", "a" + CC + AT + "o"),
    _par("a" + "coes", "a" + CC + OT + "es"),
    _par("n" + "ao", "n" + AT + "o"),
    _par("func" + "ao", "fun" + CC + AT + "o"),
    _par("func" + "oes", "fun" + CC + OT + "es"),
    _par("execuc" + "ao", "execu" + CC + AT + "o"),
    _par("execuc" + "oes", "execu" + CC + OT + "es"),
    _par("descric" + "ao", "descri" + CC + AT + "o"),
    _par("descric" + "oes", "descri" + CC + OT + "es"),
    _par("configurac" + "ao", "configura" + CC + AT + "o"),
    _par("configurac" + "oes", "configura" + CC + OT + "es"),
    _par("operac" + "ao", "opera" + CC + AT + "o"),
    _par("operac" + "oes", "opera" + CC + OT + "es"),
    _par("informac" + "ao", "informa" + CC + AT + "o"),
    _par("informac" + "oes", "informa" + CC + OT + "es"),
    _par("validac" + "ao", "valida" + CC + AT + "o"),
    _par("validac" + "oes", "valida" + CC + OT + "es"),
    _par("instalac" + "ao", "instala" + CC + AT + "o"),
    _par("instalac" + "oes", "instala" + CC + OT + "es"),
    _par("remoc" + "ao", "remo" + CC + AT + "o"),
    _par("remoc" + "oes", "remo" + CC + OT + "es"),
    _par("selec" + "ao", "sele" + CC + AT + "o"),
    _par("selec" + "oes", "sele" + CC + OT + "es"),
    _par("atenc" + "ao", "aten" + CC + AT + "o"),
    _par("direc" + "ao", "dire" + CC + AT + "o"),
    _par("verificac" + "ao", "verifica" + CC + AT + "o"),
    _par("verificac" + "oes", "verifica" + CC + OT + "es"),
    _par("criac" + "ao", "cria" + CC + AT + "o"),
    _par("criac" + "oes", "cria" + CC + OT + "es"),
    _par("opc" + "ao", "op" + CC + AT + "o"),
    _par("opc" + "oes", "op" + CC + OT + "es"),
    _par("produc" + "ao", "produ" + CC + AT + "o"),
    _par("conex" + "ao", "cone" + "x" + AT + "o"),
    _par("conex" + "oes", "cone" + "x" + OT + "es"),
    _par("vers" + "ao", "vers" + AT + "o"),
    _par("vers" + "oes", "vers" + OT + "es"),
    _par("padr" + "ao", "padr" + AT + "o"),
    _par("padr" + "oes", "padr" + OT + "es"),
    _par("sess" + "ao", "sess" + AT + "o"),
    _par("sess" + "oes", "sess" + OT + "es"),
    _par("impress" + "ao", "impress" + AT + "o"),
    _par("impress" + "oes", "impress" + OT + "es"),
    _par("express" + "ao", "express" + AT + "o"),
    _par("express" + "oes", "express" + OT + "es"),
    _par("dimens" + "ao", "dimens" + AT + "o"),
    _par("dimens" + "oes", "dimens" + OT + "es"),
    _par("tens" + "ao", "tens" + AT + "o"),
    _par("divis" + "ao", "divis" + AT + "o"),
    _par("decis" + "ao", "decis" + AT + "o"),
    _par("precis" + "ao", "precis" + AT + "o"),
    _par("revis" + "ao", "revis" + AT + "o"),
    _par("televis" + "ao", "televis" + AT + "o"),
    _par("transmiss" + "ao", "transmiss" + AT + "o"),
    _par("permiss" + "ao", "permiss" + AT + "o"),
    _par("permiss" + "oes", "permiss" + OT + "es"),
    _par("comiss" + "ao", "comiss" + AT + "o"),
    _par("colis" + "ao", "colis" + AT + "o"),
    _par("eros" + "ao", "eros" + AT + "o"),
    _par("explos" + "ao", "explos" + AT + "o"),
    _par("conclus" + "ao", "conclus" + AT + "o"),
    _par("inclus" + "ao", "inclus" + AT + "o"),
    _par("exclus" + "ao", "exclus" + AT + "o"),
    _par("confus" + "ao", "confus" + AT + "o"),
    _par("invas" + "ao", "invas" + AT + "o"),
    _par("evas" + "ao", "evas" + AT + "o"),
    _par("ocas" + "iao", "ocasi" + AT + "o"),
    _par("compreens" + "ao", "compreens" + AT + "o"),
    _par("extens" + "ao", "extens" + AT + "o"),
    _par("extens" + "oes", "extens" + OT + "es"),
    _par("suspens" + "ao", "suspens" + AT + "o"),
    _par("aplicac" + "ao", "aplica" + CC + AT + "o"),
    _par("aplicac" + "oes", "aplica" + CC + OT + "es"),
    _par("comunicac" + "ao", "comunica" + CC + AT + "o"),
    _par("comunicac" + "oes", "comunica" + CC + OT + "es"),
    _par("indicac" + "ao", "indica" + CC + AT + "o"),
    _par("indicac" + "oes", "indica" + CC + OT + "es"),
    _par("implementac" + "ao", "implementa" + CC + AT + "o"),
    _par("implementac" + "oes", "implementa" + CC + OT + "es"),
    _par("apresentac" + "ao", "apresenta" + CC + AT + "o"),
    _par("representac" + "ao", "representa" + CC + AT + "o"),
    _par("documentac" + "ao", "documenta" + CC + AT + "o"),
    _par("documentac" + "oes", "documenta" + CC + OT + "es"),
    _par("manutenc" + "ao", "manuten" + CC + AT + "o"),
    _par("prevenc" + "ao", "preven" + CC + AT + "o"),
    _par("intenc" + "ao", "inten" + CC + AT + "o"),
    _par("intervenc" + "ao", "interven" + CC + AT + "o"),
    _par("notificac" + "ao", "notifica" + CC + AT + "o"),
    _par("notificac" + "oes", "notifica" + CC + OT + "es"),
    _par("autenticac" + "ao", "autentica" + CC + AT + "o"),
    _par("autorizac" + "ao", "autoriza" + CC + AT + "o"),
    _par("organizac" + "ao", "organiza" + CC + AT + "o"),
    _par("organizac" + "oes", "organiza" + CC + OT + "es"),
    _par("utilizac" + "ao", "utiliza" + CC + AT + "o"),
    _par("atualizac" + "ao", "atualiza" + CC + AT + "o"),
    _par("inicializac" + "ao", "inicializa" + CC + AT + "o"),
    _par("finalizac" + "ao", "finaliza" + CC + AT + "o"),
    _par("serializac" + "ao", "serializa" + CC + AT + "o"),
    _par("sincronizac" + "ao", "sincroniza" + CC + AT + "o"),
    _par("otimizac" + "ao", "otimiza" + CC + AT + "o"),
    _par("geracao", "gera" + CC + AT + "o"),
    _par("geracoes", "gera" + CC + OT + "es"),
    _par("integrac" + "ao", "integra" + CC + AT + "o"),
    _par("integrac" + "oes", "integra" + CC + OT + "es"),
    _par("migrac" + "ao", "migra" + CC + AT + "o"),
    _par("migrac" + "oes", "migra" + CC + OT + "es"),
    _par("iterac" + "ao", "itera" + CC + AT + "o"),
    _par("iterac" + "oes", "itera" + CC + OT + "es"),
    _par("interac" + "ao", "intera" + CC + AT + "o"),
    _par("interac" + "oes", "intera" + CC + OT + "es"),
    _par("relac" + "ao", "rela" + CC + AT + "o"),
    _par("relac" + "oes", "rela" + CC + OT + "es"),
    _par("correlac" + "ao", "correla" + CC + AT + "o"),
    _par("populac" + "ao", "popula" + CC + AT + "o"),
    _par("alocac" + "ao", "aloca" + CC + AT + "o"),
    _par("dedicac" + "ao", "dedica" + CC + AT + "o"),
    _par("complicac" + "ao", "complica" + CC + AT + "o"),
    _par("replicac" + "ao", "replica" + CC + AT + "o"),
    _par("multiplicac" + "ao", "multiplica" + CC + AT + "o"),
    _par("modificac" + "ao", "modifica" + CC + AT + "o"),
    _par("modificac" + "oes", "modifica" + CC + OT + "es"),
    _par("especificac" + "ao", "especifica" + CC + AT + "o"),
    _par("especificac" + "oes", "especifica" + CC + OT + "es"),
    _par("classificac" + "ao", "classifica" + CC + AT + "o"),
    _par("identificac" + "ao", "identifica" + CC + AT + "o"),
    _par("quantificac" + "ao", "quantifica" + CC + AT + "o"),
    _par("notific" + "ao", "notifi" + CC + AT + "o"),
    _par("eliminac" + "ao", "elimina" + CC + AT + "o"),
    _par("terminac" + "ao", "termina" + CC + AT + "o"),
    _par("determinac" + "ao", "determina" + CC + AT + "o"),
    _par("coordenac" + "ao", "coordena" + CC + AT + "o"),
    _par("subordinac" + "ao", "subordina" + CC + AT + "o"),
    _par("observac" + "ao", "observa" + CC + AT + "o"),
    _par("observac" + "oes", "observa" + CC + OT + "es"),
    _par("conservac" + "ao", "conserva" + CC + AT + "o"),
    _par("preservac" + "ao", "preserva" + CC + AT + "o"),
    _par("reservac" + "ao", "reserva" + CC + AT + "o"),
    _par("alterac" + "ao", "altera" + CC + AT + "o"),
    _par("alterac" + "oes", "altera" + CC + OT + "es"),
    _par("aceitac" + "ao", "aceita" + CC + AT + "o"),
    _par("limitac" + "ao", "limita" + CC + AT + "o"),
    _par("limitac" + "oes", "limita" + CC + OT + "es"),
    _par("solicitac" + "ao", "solicita" + CC + AT + "o"),
    _par("negociac" + "ao", "negocia" + CC + AT + "o"),
    _par("inovac" + "ao", "inova" + CC + AT + "o"),
    _par("aprovac" + "ao", "aprova" + CC + AT + "o"),
    _par("ativac" + "ao", "ativa" + CC + AT + "o"),
    _par("desativac" + "ao", "desativa" + CC + AT + "o"),
    _par("inativac" + "ao", "inativa" + CC + AT + "o"),
    _par("motivac" + "ao", "motiva" + CC + AT + "o"),
    _par("derivac" + "ao", "deriva" + CC + AT + "o"),
    _par("privac" + "ao", "priva" + CC + AT + "o"),
    _par("captac" + "ao", "capta" + CC + AT + "o"),
    _par("adaptac" + "ao", "adapta" + CC + AT + "o"),
    _par("aceitac" + "oes", "aceita" + CC + OT + "es"),
    _par("reputac" + "ao", "reputa" + CC + AT + "o"),
    _par("execuc" + "oes", "execu" + CC + OT + "es"),
    _par("cooperac" + "ao", "coopera" + CC + AT + "o"),
    _par("colaborac" + "ao", "colabora" + CC + AT + "o"),
    _par("elaborac" + "ao", "elabora" + CC + AT + "o"),
    _par("evaporac" + "ao", "evapora" + CC + AT + "o"),
    _par("exploracao", "explora" + CC + AT + "o"),
    _par("importac" + "ao", "importa" + CC + AT + "o"),
    _par("exportac" + "ao", "exporta" + CC + AT + "o"),
    _par("deportac" + "ao", "deporta" + CC + AT + "o"),
    _par("transportac" + "ao", "transporta" + CC + AT + "o"),
    _par("transformac" + "ao", "transforma" + CC + AT + "o"),
    _par("formac" + "ao", "forma" + CC + AT + "o"),
    _par("reformac" + "ao", "reforma" + CC + AT + "o"),
    _par("informac" + "oes", "informa" + CC + OT + "es"),
    _par("nomeac" + "ao", "nomea" + CC + AT + "o"),
    _par("situac" + "ao", "situa" + CC + AT + "o"),
    _par("situac" + "oes", "situa" + CC + OT + "es"),
    _par("diretor" + "io", "diret" + O_ + "rio"),
    _par("diretor" + "ios", "diret" + O_ + "rios"),
    _par("reposit" + "orio", "reposit" + O_ + "rio"),
    _par("reposit" + "orios", "reposit" + O_ + "rios"),
    _par("hist" + "orico", "hist" + O_ + "rico"),
    _par("hist" + "oricos", "hist" + O_ + "ricos"),
    _par("obrig" + "atorio", "obrig" + "at" + O_ + "rio"),
    _par("obrig" + "atorios", "obrig" + "at" + O_ + "rios"),
    _par("trans" + "itorio", "trans" + "it" + O_ + "rio"),
    _par("crit" + "ico", "cr" + I_ + "tico"),
    _par("crit" + "ica", "cr" + I_ + "tica"),
    _par("crit" + "icos", "cr" + I_ + "ticos"),
    _par("crit" + "icas", "cr" + I_ + "ticas"),
    _par("ult" + "imo", U + "ltimo"),
    _par("ult" + "imos", U + "ltimos"),
    _par("ult" + "ima", U + "ltima"),
    _par("ult" + "imas", U + "ltimas"),
    _par("prox" + "imo", "pr" + O_ + "ximo"),
    _par("prox" + "imos", "pr" + O_ + "ximos"),
    _par("prox" + "ima", "pr" + O_ + "xima"),
    _par("prox" + "imas", "pr" + O_ + "ximas"),
    _par("peri" + "odo", "per" + I_ + "odo"),
    _par("peri" + "odos", "per" + I_ + "odos"),
    _par("un" + "ico", U + "nico"),
    _par("un" + "ica", U + "nica"),
    _par("un" + "icos", U + "nicos"),
    _par("un" + "icas", U + "nicas"),
    _par("m" + "inimo", "m" + I_ + "nimo"),
    _par("m" + "aximo", "m" + "á" + "ximo"),
    _par("m" + "edio", "m" + E + "dio"),
    _par("m" + "edia", "m" + E + "dia"),
    _par("m" + "etodo", "m" + E + "todo"),
    _par("m" + "etodos", "m" + E + "todos"),
    _par("m" + "odulo", "m" + O_ + "dulo"),
    _par("m" + "odulos", "m" + O_ + "dulos"),
    _par("p" + "agina", "p" + "á" + "gina"),
    _par("p" + "aginas", "p" + "á" + "ginas"),
    _par("v" + "arias", "v" + "á" + "rias"),
    _par("v" + "arios", "v" + "á" + "rios"),
    _par("pr" + "aticas", "pr" + "á" + "ticas"),
    _par("pr" + "atica", "pr" + "á" + "tica"),
    _par("pr" + "atico", "pr" + "á" + "tico"),
    _par("pr" + "aticos", "pr" + "á" + "ticos"),
    _par("autom" + "atico", "autom" + "á" + "tico"),
    _par("autom" + "atica", "autom" + "á" + "tica"),
    _par("pol" + "itica", "pol" + I_ + "tica"),
    _par("pol" + "iticas", "pol" + I_ + "ticas"),
    _par("l" + "ogica", "l" + O_ + "gica"),
    _par("l" + "ogico", "l" + O_ + "gico"),
    _par("l" + "ogicas", "l" + O_ + "gicas"),
    _par("c" + "odigo", "c" + O_ + "digo"),
    _par("c" + "odigos", "c" + O_ + "digos"),
    _par("anal" + "ise", "an" + "á" + "lise"),
    _par("anal" + "ises", "an" + "á" + "lises"),
    _par("b" + "asico", "b" + "á" + "sico"),
    _par("b" + "asica", "b" + "á" + "sica"),
    _par("t" + "ecnico", "t" + E + "cnico"),
    _par("t" + "ecnica", "t" + E + "cnica"),
    _par("t" + "ecnicas", "t" + E + "cnicas"),
    _par("t" + "ecnicos", "t" + E + "cnicos"),
    _par("din" + "amico", "din" + AC + "mico"),
    _par("din" + "amica", "din" + AC + "mica"),
    _par("est" + "atico", "est" + "á" + "tico"),
    _par("est" + "atica", "est" + "á" + "tica"),
    _par("us" + "uario", "us" + "u" + "á" + "rio"),
    _par("us" + "uarios", "us" + "u" + "á" + "rios"),
    _par("necess" + "ario", "necess" + "á" + "rio"),
    _par("necess" + "arios", "necess" + "á" + "rios"),
    _par("prim" + "ario", "prim" + "á" + "rio"),
    _par("secund" + "ario", "secund" + "á" + "rio"),
    _par("tern" + "ario", "tern" + "á" + "rio"),
    _par("bin" + "ario", "bin" + "á" + "rio"),
    _par("bin" + "arios", "bin" + "á" + "rios"),
    _par("salv" + "ario", "salv" + "á" + "rio"),
    _par("pr" + "opria", "pr" + O_ + "pria"),
    _par("pr" + "oprio", "pr" + O_ + "prio"),
    _par("impr" + "oprio", "impr" + O_ + "prio"),
    _par("f" + "isico", "f" + I_ + "sico"),
    _par("f" + "isica", "f" + I_ + "sica"),
    _par("m" + "usica", "m" + U + "sica"),
    _par("m" + "usicas", "m" + U + "sicas"),
    _par("f" + "acil", "f" + "á" + "cil"),
    _par("dif" + "icil", "dif" + I_ + "cil"),
    _par("dif" + "iceis", "dif" + I_ + "ceis"),
    _par("impr" + "essao", "impr" + "ess" + AT + "o"),
    _par("conte" + "udo", "conte" + U + "do"),
    _par("conte" + "udos", "conte" + U + "dos"),
    _par("depend" + "encia", "depend" + EC + "ncia"),
    _par("depend" + "encias", "depend" + EC + "ncias"),
    _par("frequ" + "encia", "frequ" + EC + "ncia"),
    _par("refer" + "encia", "refer" + EC + "ncia"),
    _par("refer" + "encias", "refer" + EC + "ncias"),
    _par("prefer" + "encia", "prefer" + EC + "ncia"),
    _par("trans" + "ferencia", "trans" + "fer" + EC + "ncia"),
    _par("exist" + "encia", "exist" + EC + "ncia"),
    _par("persist" + "encia", "persist" + EC + "ncia"),
    _par("resist" + "encia", "resist" + EC + "ncia"),
    _par("assist" + "encia", "assist" + EC + "ncia"),
    _par("tend" + "encia", "tend" + EC + "ncia"),
    _par("presenc" + "a", "presen" + CC + "a"),
    _par("ausenc" + "ia", "aus" + EC + "ncia"),
    _par("preced" + "encia", "preced" + EC + "ncia"),
    _par("inflien" + "cia", "influ" + EC + "ncia"),
    _par("conseq" + "uencia", "conseq" + U + "" + EC + "ncia"),
    _par("pot" + "encia", "pot" + EC + "ncia"),
    _par("pot" + "encias", "pot" + EC + "ncias"),
    _par("agenc" + "ia", "ag" + EC + "ncia"),
    _par("emerg" + "encia", "emerg" + EC + "ncia"),
    _par("diverg" + "encia", "diverg" + EC + "ncia"),
    _par("converg" + "encia", "converg" + EC + "ncia"),
    _par("urg" + "encia", "urg" + EC + "ncia"),
    _par("consci" + "encia", "consci" + EC + "ncia"),
    _par("paci" + "encia", "paci" + EC + "ncia"),
    _par("experi" + "encia", "experi" + EC + "ncia"),
    _par("experi" + "encias", "experi" + EC + "ncias"),
    _par("audi" + "encia", "audi" + EC + "ncia"),
    _par("obedi" + "encia", "obedi" + EC + "ncia"),
    _par("diferenc" + "a", "diferen" + CC + "a"),
    _par("diferenc" + "as", "diferen" + CC + "as"),
    _par("prefer" + "encia", "prefer" + EC + "ncia"),
    _par("provid" + "encia", "provid" + EC + "ncia"),
    _par("serv" + "ico", "servi" + CC + "o"),
    _par("serv" + "icos", "servi" + CC + "os"),
    _par("prec" + "o", "pre" + CC + "o"),
    _par("esfor" + "co", "esfor" + CC + "o"),
    _par("cora" + "cao", "cora" + CC + AT + "o"),
    _par("cora" + "coes", "cora" + CC + OT + "es"),
    _par("pao", "p" + AT + "o"),
    _par("maos", "m" + AT + "os"),
    _par("mao", "m" + AT + "o"),
    _par("irm" + "ao", "irm" + AT + "o"),
    _par("irm" + "aos", "irm" + AT + "os"),
    _par("irm" + "a", "irm" + AT),
    _par("am" + "anha", "a" + "manh" + AT),
    _par("manh" + "a", "manh" + AT),
    _par("tamb" + "em", "tamb" + E + "m"),
    _par("port" + "ugues", "portugu" + EC + "s"),
    _par("ingl" + "es", "ingl" + EC + "s"),
    _par("franc" + "es", "franc" + EC + "s"),
    _par("chin" + "es", "chin" + EC + "s"),
    _par("tr" + "es", "tr" + EC + "s"),
    _par("m" + "es", "m" + EC + "s"),
    _par("voc" + "e", "voc" + EC),
    _par("gr" + "afico", "gr" + "á" + "fico"),
    _par("gr" + "aficos", "gr" + "á" + "ficos"),
    _par("est" + "rategia", "est" + "rat" + E + "gia"),
]

_vistos: set[str] = set()
_CORRECOES: dict[str, str] = {}
for errada, correta in _PARES:
    key = errada.lower()
    if errada and correta and errada != correta and key not in _vistos:
        _vistos.add(key)
        _CORRECOES[errada] = correta

WHITELIST_PATTERNS: list[str] = [
    r"^VALIDATOR_BRIEF\.md$",
    r"^LICENSE$",
    r"^NOTICE$",
    r"^CHANGELOG\.md$",
    r"^tests/fixtures/.*",
    r"^docs/history/.*",
    r"^docs/research/.*",
    r"^scripts/validar-acentuacao\.py$",
    r"^scripts/check_anonymity\.sh$",
    r"^tests/unit/test_validar_acentuacao\.py$",
    r"^tests/unit/test_acentuacao_uma_passada_so\.py$",
    r"\.json$",
    r"\.lock$",
    r"^\.git/.*",
    r"^\.venv/.*",
    r"^venv/.*",
    r"^node_modules/.*",
    r"^__pycache__/.*",
    r".*/__pycache__/.*",
    r".*\.pyc$",
    r".*\.png$",
    r".*\.svg$",
    r".*\.ico$",
    r".*\.desktop$",
    r".*\.service$",
    r".*\.rules$",
    r".*\.glade$",
    r".*\.bin$",
]
_WHITELIST_RE = [re.compile(p) for p in WHITELIST_PATTERNS]

EXTENSOES_ALVO = (
    ".py", ".sh", ".zsh", ".bash",
    ".md", ".yml", ".yaml", ".toml",
    ".cfg", ".ini", ".txt", ".csv",
)


def is_whitelisted(rel_path: str) -> bool:
    rel = rel_path.replace("\\", "/")
    return any(pat.search(rel) for pat in _WHITELIST_RE)


_IDENT_CHAR = re.compile(r"[A-Za-z0-9_]")


def _is_uppercase_snake_token(line: str, start: int, end: int) -> bool:
    """Verifica se a palavra casada faz parte de um identificador em UPPERCASE_SNAKE."""
    i = start
    while i > 0 and _IDENT_CHAR.match(line[i - 1]):
        i -= 1
    j = end
    while j < len(line) and _IDENT_CHAR.match(line[j]):
        j += 1
    token = line[i:j]
    letras = [c for c in token if c.isalpha()]
    if not letras:
        return False
    return all(c.isupper() for c in letras)


def _esta_em_identificador_snake(line: str, start: int, end: int) -> bool:
    """Detecta se a palavra está dentro de identificador snake_case maior."""
    antes = line[start - 1] if start > 0 else ""
    depois = line[end] if end < len(line) else ""
    sep = {"_", ".", "-", "$", "{", "=", "/", "@"}
    depois2 = line[end + 1] if end + 1 < len(line) else ""
    if depois == "." and not _IDENT_CHAR.match(depois2 or " "):
        depois = ""
    if antes in sep or depois in sep:
        return True
    if antes in {'"', "'"} and start >= 2 and line[start - 2] == "=":
        return True
    prefix = line[:start].rstrip()
    for kw in ("def ", "class ", "alias ", "function ", "local "):
        if prefix.endswith(kw.strip()):
            return True
    return False


def _compila_pattern(errada: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(errada)}(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )


_PATTERNS: dict[str, re.Pattern[str]] = {e: _compila_pattern(e) for e in _CORRECOES}

_cache_alternancia: tuple[tuple[int, int], re.Pattern[str]] | None = None


def _alternancia() -> re.Pattern[str]:
    """Um único padrão com as 314 palavras, em vez de 314 padrões por linha."""
    global _cache_alternancia
    chave = (id(_CORRECOES), len(_CORRECOES))
    if _cache_alternancia is not None and _cache_alternancia[0] == chave:
        return _cache_alternancia[1]
    pat = re.compile(
        r"(?<![A-Za-z0-9_])(?:"
        + "|".join(re.escape(e) for e in sorted(_CORRECOES, key=len, reverse=True))
        + r")(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )
    _cache_alternancia = (chave, pat)
    return pat


UNICODE_ALLOWED_RANGES: tuple[tuple[int, int], ...] = (
    (0x2190, 0x21FF),
    (0x2500, 0x257F),
    (0x2580, 0x259F),
    (0x25A0, 0x25FF),
)


def is_protected_codepoint(cp: int) -> bool:
    """True se `cp` pertence a bloco Unicode protegido por ADR-011."""
    return any(lo <= cp <= hi for lo, hi in UNICODE_ALLOWED_RANGES)


def _contem_glyph_protegido(texto: str) -> bool:
    """True se `texto` contém ao menos um caractere em UNICODE_ALLOWED_RANGES."""
    return any(is_protected_codepoint(ord(c)) for c in texto)


def _linhas_markdown_codigo(linhas: list[str]) -> set[int]:
    """Retorna índices (0-based) de linhas dentro de fenced code block ou indentado 4+."""
    dentro_fenced = False
    fence_set: set[int] = set()
    for idx, ln in enumerate(linhas):
        stripped = ln.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence_set.add(idx)
            dentro_fenced = not dentro_fenced
            continue
        if dentro_fenced:
            fence_set.add(idx)
    indent_set: set[int] = set()
    prev_vazia = True
    bloco_ativo = False
    for idx, ln in enumerate(linhas):
        if ln.strip() == "":
            prev_vazia = True
            bloco_ativo = False
            continue
        if prev_vazia and (ln.startswith("    ") or ln.startswith("\t")):
            bloco_ativo = True
        if bloco_ativo and (ln.startswith("    ") or ln.startswith("\t")):
            indent_set.add(idx)
        else:
            bloco_ativo = False
        prev_vazia = False
    return fence_set | indent_set


_INLINE_CODE_MD = re.compile(r"`[^`\n]+`")


def _mascara_inline_code_md(linha: str) -> str:
    """Em markdown, substitui conteúdo de `...` por espaços de mesmo tamanho."""
    def _sub(m: re.Match[str]) -> str:
        return " " * len(m.group())
    return _INLINE_CODE_MD.sub(_sub, linha)


def _mascara_chaves_da_fstring(literal: str) -> str:
    """No 3.10 e no 3.11, apaga o CÓDIGO das chaves de uma f-string."""
    i = 0
    while i < len(literal) and literal[i] not in "'\"":
        i += 1
    prefixo = literal[:i].lower()
    if "f" not in prefixo or i >= len(literal):
        return literal
    aspas = literal[i : i + 3] if literal[i : i + 3] in ('"""', "'''") else literal[i]
    ini = i + len(aspas)
    fim = len(literal) - len(aspas)
    if fim < ini:
        return literal
    cru = "r" in prefixo
    saida = list(literal)

    def apagar(a: int, b: int) -> None:
        for k in range(a, b):
            if saida[k] != "\n":
                saida[k] = " "

    def string_de_dentro(j: int) -> int:
        """`j` é a aspa de uma string da expressão; ela é TEXTO e fica."""
        comeco = j
        while comeco > 0 and j - comeco < 2 and literal[comeco - 1] in "rRbBuUfF":
            comeco -= 1
        if comeco > 0 and (literal[comeco - 1].isalnum() or literal[comeco - 1] == "_"):
            comeco = j
        q = literal[j : j + 3] if literal[j : j + 3] in ('"""', "'''") else literal[j]
        k = j + len(q)
        while k < fim and not literal.startswith(q, k):
            k += 2 if literal[k] == "\\" else 1
        k = min(k + len(q), fim)
        if "f" in literal[comeco:j].lower():
            saida[comeco:k] = _mascara_chaves_da_fstring(literal[comeco:k])
        else:
            saida[comeco:j] = literal[comeco:j]
        return k

    def especificacao(j: int) -> int:
        """Depois do `:`: texto, com campos aninhados. Volta após a `}`."""
        k = j
        while k < fim:
            if literal[k] == "{":
                apagar(k, k + 1)
                k = campo(k + 1)
                continue
            if literal[k] == "}":
                apagar(k, k + 1)
                return k + 1
            k += 1
        return fim

    def campo(j: int) -> int:
        """Depois da `{`: código até o `:` ou a `}` de mesma profundidade."""
        profundidade = 0
        codigo = j
        k = j
        while k < fim:
            c = literal[k]
            if c in "'\"":
                apagar(codigo, k)
                k = codigo = string_de_dentro(k)
                continue
            if c in "([{":
                profundidade += 1
            elif c in ")]" or (c == "}" and profundidade > 0):
                profundidade -= 1
            elif c == "}":
                apagar(codigo, k + 1)
                return k + 1
            elif c == ":" and profundidade == 0:
                apagar(codigo, k + 1)
                return especificacao(k + 1)
            k += 1
        apagar(codigo, fim)
        return fim

    apagar(0, ini)
    apagar(fim, len(literal))
    k = ini
    while k < fim:
        c = literal[k]
        if c == "\\" and not cru:
            if literal[k + 1 : k + 3] == "N{":
                fecha = literal.find("}", k + 3, fim)
                k = fim if fecha < 0 else fecha + 1
            else:
                k += 2
            continue
        if c == "{" and literal[k + 1 : k + 2] != "{":
            apagar(k, k + 1)
            k = campo(k + 1)
            continue
        if c in "{}" and literal[k + 1 : k + 2] == c:
            apagar(k + 1, k + 2)
            k += 2
            continue
        k += 1
    return "".join(saida)


def _sobrepor(
    mascarado: list[str], linhas: list[str], inicio: tuple[int, int], texto: str
) -> None:
    """Escreve `texto` (já mascarado) sobre as linhas, a partir de `inicio`."""
    lin_ini, col_ini = inicio
    for k, pedaco in enumerate(texto.split("\n")):
        i = lin_ini - 1 + k
        if not 0 <= i < len(linhas):
            continue
        comeco = col_ini if k == 0 else 0
        fim = min(comeco + len(pedaco), len(linhas[i]))
        mascarado[i] = (
            mascarado[i][:comeco] + pedaco[: fim - comeco] + mascarado[i][fim:]
        )


def _mascara_codigo_python(conteudo: str, linhas: list[str]) -> list[str]:
    """Em ``.py``, apaga tudo que NÃO é comentário/string antes da varredura."""
    import io
    import tokenize

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(conteudo).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError, ValueError):
        return linhas

    tipos_texto = {tokenize.COMMENT, tokenize.STRING}
    fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", None)
    if fstring_middle is not None:
        tipos_texto.add(fstring_middle)

    mascarado = [" " * len(linha) for linha in linhas]
    for tok in tokens:
        if tok.type not in tipos_texto:
            continue
        if fstring_middle is None and tok.type == tokenize.STRING:
            so_texto = _mascara_chaves_da_fstring(tok.string)
            if so_texto is not tok.string:
                _sobrepor(mascarado, linhas, tok.start, so_texto)
                continue
        (lin_ini, col_ini), (lin_fim, col_fim) = tok.start, tok.end
        for n in range(lin_ini, lin_fim + 1):
            i = n - 1
            if not 0 <= i < len(linhas):
                continue
            original = linhas[i]
            inicio = col_ini if n == lin_ini else 0
            fim = col_fim if n == lin_fim else len(original)
            fim = min(fim, len(original))
            mascarado[i] = (
                mascarado[i][:inicio]
                + original[inicio:fim]
                + mascarado[i][fim:]
            )
    return mascarado


def checar_arquivo(path: Path, raiz: Path) -> list[tuple[int, str, str, str]]:
    """Retorna lista de (linha, palavra_errada, palavra_correta, texto_da_linha)."""
    try:
        rel = str(path.resolve().relative_to(raiz))
    except ValueError:
        rel = str(path)

    if is_whitelisted(rel):
        return []

    if path.suffix.lower() not in EXTENSOES_ALVO:
        return []

    try:
        conteudo = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    linhas = conteudo.splitlines()
    pular_idx: set[int] = set()
    eh_markdown = path.suffix.lower() == ".md"
    if eh_markdown:
        pular_idx = _linhas_markdown_codigo(linhas)
    eh_python = path.suffix.lower() == ".py"
    linhas_texto = _mascara_codigo_python(conteudo, linhas) if eh_python else linhas

    violacoes: list[tuple[int, str, str, str]] = []
    for idx, linha in enumerate(linhas):
        if idx in pular_idx:
            continue
        if "noqa-acento" in linha or "noqa: acentuacao" in linha:
            continue
        if eh_markdown:
            linha_busca = _mascara_inline_code_md(linha)
        elif eh_python:
            linha_busca = linhas_texto[idx]
        else:
            linha_busca = linha
        for m in _alternancia().finditer(linha_busca):
            correta = _CORRECOES.get(m.group().lower())
            if correta is None:
                continue
            if _is_uppercase_snake_token(linha_busca, m.start(), m.end()):
                continue
            if _esta_em_identificador_snake(linha_busca, m.start(), m.end()):
                continue
            if m.group().lower() == correta.lower():
                continue
            violacoes.append((idx + 1, m.group(), correta, linha.strip()))
    return violacoes


def corrigir_arquivo(path: Path, raiz: Path) -> int:
    """Aplica substituições in-place no arquivo, respeitando os mesmos skips."""
    try:
        rel = str(path.resolve().relative_to(raiz))
    except ValueError:
        rel = str(path)

    if is_whitelisted(rel):
        return 0

    if path.suffix.lower() not in EXTENSOES_ALVO:
        return 0

    try:
        conteudo = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return 0

    linhas = conteudo.splitlines(keepends=True)
    eh_markdown = path.suffix.lower() == ".md"
    linhas_sem_sep = conteudo.splitlines()
    pular_idx: set[int] = set()
    if eh_markdown:
        pular_idx = _linhas_markdown_codigo(linhas_sem_sep)

    total_subs = 0
    novas_linhas: list[str] = []
    for idx, linha_com_sep in enumerate(linhas):
        if linha_com_sep.endswith("\r\n"):
            sep = "\r\n"
            linha = linha_com_sep[:-2]
        elif linha_com_sep.endswith("\n"):
            sep = "\n"
            linha = linha_com_sep[:-1]
        else:
            sep = ""
            linha = linha_com_sep

        if idx in pular_idx:
            novas_linhas.append(linha_com_sep)
            continue
        if "noqa-acento" in linha or "noqa: acentuacao" in linha:
            novas_linhas.append(linha_com_sep)
            continue

        if _contem_glyph_protegido(linha):
            novas_linhas.append(linha_com_sep)
            continue

        linha_busca = _mascara_inline_code_md(linha) if eh_markdown else linha

        subs: list[tuple[int, int, str]] = []
        for m in _alternancia().finditer(linha_busca):
            correta = _CORRECOES.get(m.group().lower())
            if correta is None:
                continue
            if _is_uppercase_snake_token(linha_busca, m.start(), m.end()):
                continue
            if _esta_em_identificador_snake(linha_busca, m.start(), m.end()):
                continue
            if m.group().lower() == correta.lower():
                continue
            original = m.group()
            rep = (
                correta[:1].upper() + correta[1:]
                if original[:1].isupper()
                else correta
            )
            subs.append((m.start(), m.end(), rep))

        if subs:
            filtrados = [
                (s, e, r) for s, e, r in subs
                if not _contem_glyph_protegido(linha[s:e])
            ]
            if len(filtrados) != len(subs):
                rejeitados = [linha[s:e] for s, e, _ in subs
                              if _contem_glyph_protegido(linha[s:e])]
                print(
                    f"[ADR-011] {path}:{idx + 1} — "
                    f"{len(subs) - len(filtrados)} substituição(ões) rejeitada(s) "
                    f"por tocar glyph protegido: {rejeitados!r}",
                    file=sys.stderr,
                )
            subs = filtrados

        if subs:
            subs.sort(key=lambda t: t[0])
            aceitas: list[tuple[int, int, str]] = []
            ultimo_end = -1
            for s, e, r in subs:
                if s >= ultimo_end:
                    aceitas.append((s, e, r))
                    ultimo_end = e
            nova = linha
            for s, e, r in reversed(aceitas):
                nova = nova[:s] + r + nova[e:]
            if _contem_glyph_protegido(linha) and not _contem_glyph_protegido(nova):
                perdidos = sorted(
                    {c for c in linha if is_protected_codepoint(ord(c))} - set(nova)
                )
                print(
                    f"[ADR-011 POST] {path}:{idx + 1} — revertido "
                    f"(glyph(s) perdido(s) apos substituicao: {perdidos!r})",
                    file=sys.stderr,
                )
                novas_linhas.append(linha_com_sep)
                continue
            total_subs += len(aceitas)
            novas_linhas.append(nova + sep)
        else:
            novas_linhas.append(linha_com_sep)

    if total_subs:
        path.write_text("".join(novas_linhas), encoding="utf-8")
    return total_subs


def listar_arquivos_git(raiz: Path) -> list[Path]:
    """Lista os arquivos que o modo ``--all`` deve varrer."""
    try:
        out = subprocess.check_output(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            cwd=str(raiz),
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    arquivos: list[Path] = []
    vistos: set[Path] = set()
    for nome in out.split("\x00"):
        if not nome:
            continue
        p = raiz / nome
        if p in vistos:
            continue
        if p.is_file() and p.suffix.lower() in EXTENSOES_ALVO:
            vistos.add(p)
            arquivos.append(p)
    return arquivos


def descobrir_raiz() -> Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
        return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument(
        "--all",
        action="store_true",
        help="Varre todo o repo via git ls-files",
    )
    grp.add_argument(
        "--check-file",
        metavar="PATH",
        nargs="+",
        help="Varre um ou mais arquivos (modo pre-commit)",
    )
    grp.add_argument(
        "--show-whitelist",
        action="store_true",
        help="Imprime a whitelist de paths e sai",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Arquivos a varrer (padrão: --all se omitido e sem --check-file)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Aplica correções in-place via dicionário (respeita skips e whitelist)",
    )
    args = parser.parse_args()

    if args.show_whitelist:
        for p in WHITELIST_PATTERNS:
            print(p)
        return 0

    raiz = descobrir_raiz()

    recebidos: list[Path] = [Path(p) for p in (args.check_file or [])]
    recebidos.extend(args.paths)

    if args.all or not recebidos:
        alvos = listar_arquivos_git(raiz)
    else:
        alvos = []
        for p in recebidos:
            if p.is_dir():
                for ext in EXTENSOES_ALVO:
                    alvos.extend(p.rglob(f"*{ext}"))
            else:
                alvos.append(p)

    if args.fix:
        total_fix = 0
        arquivos_tocados = 0
        for arq in alvos:
            n = corrigir_arquivo(arq, raiz)
            if n:
                try:
                    rel = arq.resolve().relative_to(raiz)
                except ValueError:
                    rel = arq
                print(f"{rel}: {n} substitui{CC}{OT}es aplicadas")
                total_fix += n
                arquivos_tocados += 1
        print(
            f"\n{total_fix} corre{CC}{OT}es em {arquivos_tocados} arquivo(s).",
            file=sys.stderr,
        )
        return 0

    total = 0
    for arq in alvos:
        viols = checar_arquivo(arq, raiz)
        for linha, errada, correta, _texto in viols:
            try:
                rel = arq.resolve().relative_to(raiz)
            except ValueError:
                rel = arq
            print(f"{rel}:{linha}:{errada} -> sugest{AT}o {correta}")
            total += 1

    if total:
        msg = (
            f"\n{total} viola{CC}{AT}o(es) de acentua{CC}{AT}o "
            "PT-BR encontrada(s)."
        )
        print(msg, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
