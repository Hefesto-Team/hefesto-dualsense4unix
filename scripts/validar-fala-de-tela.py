#!/usr/bin/env python3
"""validar-fala-de-tela.py — o portão, nos dois sentidos.

Executa Z6-04 (docs/process/sprints/2026-08-24-ONDA0-Z6-COMUNHAO-COM-O-SPECS-01…
.md), a Peça 3 do contrato desenhado na
docs/process/sprints/2026-08-24-PAREAMENTO-01-a-medicao-nova-tem-de-chegar-sozinha-na-tela.md.

A DESCOBERTA DO DESENHO: "A TELA AFIRMA ALÉM DO MAPA" E "O MAPA MUDOU E
DEIXOU A TELA PARA TRÁS" SÃO A MESMA COMPARAÇÃO
--------------------------------------------------------------------------
`Fala.afirma` contra `FATOS[chave][lado]`. Não importa qual lado mudou por
último — o portão só sabe comparar os dois, e a mensagem de erro é honesta
sobre o que mudou (ver `_explica_afirma_nao_aciona` e companhia).

VARRE AS DUAS RAÍZES DE TELA — `app/` E `interface/`
-------------------------------------------------------
Desde 06/09/2026. Até então a régua conhecia só `app/`, e a tela nova mora em
`interface/`: das 170 frases de transporte que o `--censo-de-transporte` conta
hoje, **123 estavam fora do alcance** — contra 47 dentro. Pela régua mais
grossa da sprint (todo literal com mais de 25 caracteres, docstring incluída),
a proporção é a mesma: 231 em `interface/` contra 163 em `app/`.
`RAIZES_DE_TELA` é o dono desse alcance, e ele tem piso — encolher a tupla
reprova.

LÊ AS `Fala` POR AST, NUNCA IMPORTANDO O PACOTE `app/`
---------------------------------------------------------
`app/**.py` importa GTK e companhia — um runner sem essas dependências
transformaria `ImportError` em "zero `Fala` encontradas", que é o jeito
silencioso de este portão se desligar (a mesma razão escrita em
`scripts/gerar-contrato-ipc.py`). Os dois módulos de REGISTRO
(`app/fala_do_mapa.py`, `app/fatos_do_mapa.py`) são zero-dependência de
propósito — só stdlib — e ESSES dois este portão importa direto, por caminho
de arquivo, sem passar pelo `__init__.py` do pacote.

O QUE O PORTÃO NÃO COMPARA, PARA NÃO GRITAR FALSO
----------------------------------------------------
`provado_em`, `*_evidencia`, `*_detalhe`, `nota` — só as colunas de que o
`afirma` depende (`existe`, `aciona`, `por_que_nao_aciona`). Recarimbar uma
prova não acorda o portão; mudar o veredito acorda.

Uso:
    python3 scripts/validar-fala-de-tela.py --all            # roda no CI
    python3 scripts/validar-fala-de-tela.py --fila           # placeholders abertos
    python3 scripts/validar-fala-de-tela.py --exigir-prazo   # prazo vencido é FALHA
    python3 scripts/validar-fala-de-tela.py --censo-de-transporte  # o número de hoje
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parent.parent
APP_RELATIVO = "src/hefesto_dualsense4unix/app"
APP = RAIZ / APP_RELATIVO
INTERFACE_RELATIVO = "src/hefesto_dualsense4unix/interface"
FALA_DO_MAPA_RELATIVO = f"{APP_RELATIVO}/fala_do_mapa.py"
FATOS_DO_MAPA_RELATIVO = f"{APP_RELATIVO}/fatos_do_mapa.py"
MAPA_RELATIVO = "docs/data/mapa-controles.csv"

#: AS RAÍZES DE TELA — as DUAS, e a segunda entrou em 06/09/2026.
#:
#: Até esta data a régua varria só `app/`, e era a única raiz que ela conhecia.
#: `app/` continua sendo tela em parte, então nada foi trocado: `interface/`
#: foi ACRESCENTADA. Trocar uma pela outra devolveria o mesmo defeito virado
#: para o outro lado.
#:
#: O QUE ISSO DEIXAVA PASSAR, medido em 06/09/2026 com `--censo-de-transporte`:
#: 169 literais de transporte em `app/` (vistos) contra **227 em `interface/`**
#: (invisíveis). **A maior parte do texto de transporte da casa estava fora do
#: alcance da régua que existe para ele** — e não foi decisão: a régua é de
#: 24/08 e a tela nova nasceu depois, então ela mediu o mundo em que a única
#: tela era `app/`.
#:
#: A pergunta que desenterrou isto é dela, em 06/09/2026: *"olharam o mapa dos
#: controles e o csv que alimenta o specs.html?"* — e, na sequência: *"se
#: coisas assim aconteceram antes não so nessas duas sprints. entao tem coisa
#: errada."*  <!-- noqa-acento: citação literal dela -->
#:
#: Encolher esta tupla é perder alcance em silêncio, e por isso ela tem piso:
#: `PISO_DA_REGUA["raizes"]`.
RAIZES_DE_TELA: tuple[str, ...] = (APP_RELATIVO, INTERFACE_RELATIVO)

#: Z6-08 — onde `NUMEROS_MEDIDOS_NO_MAPA` mora hoje. Lido por AST, como tudo
#: neste portão: `integrations/radio_da_mesa.py` puxa `structlog` por
#: `core.sysfs_leds`, e importar o puxaria também.
NUMEROS_RELATIVO = "src/hefesto_dualsense4unix/integrations/radio_da_mesa.py"

#: Os nomes dos dois módulos de registro que este portão importa DIRETO — os
#: únicos dois, de propósito. Nunca `app/__init__.py`, nunca um arquivo de
#: tela: os dois aqui não têm import de GTK, e o teste
#: `test_os_dois_modulos_de_registro_nao_tem_dependencia_pesada` prova isso.
_MODULOS_QUE_ESTE_PORTAO_IMPORTA = (FALA_DO_MAPA_RELATIVO, FATOS_DO_MAPA_RELATIVO)


def _carrega_modulo(caminho: Path, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, caminho)
    if spec is None or spec.loader is None:  # pragma: no cover - defensivo
        raise ImportError(f"não consegui montar o spec de {caminho}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def carrega_registro(raiz: Path) -> tuple[ModuleType, ModuleType]:
    """`(fala_do_mapa, fatos_do_mapa)`, carregados por caminho de arquivo."""
    fala_do_mapa = _carrega_modulo(raiz / FALA_DO_MAPA_RELATIVO, "fala_do_mapa_lido_pelo_portao")
    fatos_do_mapa = _carrega_modulo(raiz / FATOS_DO_MAPA_RELATIVO, "fatos_do_mapa_lido_pelo_portao")
    return fala_do_mapa, fatos_do_mapa


# ─────────────────────────────────────────────────────────────────────────
# A DESCOBERTA POR AST
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class FalaEncontrada:
    arquivo: str
    linha: int
    chave: str | None
    lado: str | None
    aba: str | None
    afirma_nome: str | None
    afirma_valor: str | None
    porque: str
    texto_e_nao_medido: bool
    pendente: dict[str, object] | None
    resolvel: bool
    erro_de_leitura: str | None

    @property
    def origem(self) -> str:
        return f"{self.arquivo}:{self.linha}"


def _literal(no: ast.expr | None) -> object:
    """`ast.literal_eval`, devolvendo `None` (não levantando) se não for literal."""
    if no is None:
        return None
    try:
        return ast.literal_eval(no)
    except (ValueError, TypeError, SyntaxError):
        return None


def _e_chamada_de(no: ast.AST, nome: str) -> bool:
    return isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == nome


def _le_pendencia(no: ast.expr | None) -> dict[str, object] | None:
    if no is None or (isinstance(no, ast.Constant) and no.value is None):
        return None
    if not _e_chamada_de(no, "Pendencia"):
        return {"_nao_resolvel": True}
    assert isinstance(no, ast.Call)
    campos: dict[str, object] = {}
    for kw in no.keywords:
        if kw.arg is None:
            continue
        campos[kw.arg] = _literal(kw.value)
    return campos


def _le_fala(no: ast.Call, caminho: Path, raiz: Path) -> FalaEncontrada:
    kwargs = {kw.arg: kw.value for kw in no.keywords if kw.arg}
    # posicionais também são aceitos, na ORDEM da assinatura de `Fala`
    # (chave, lado, aba, texto, afirma, porque, pendente) — para não obrigar
    # quem escreve a nomear todo argumento.
    ordem = ("chave", "lado", "aba", "texto", "afirma", "porque", "pendente")
    for indice, arg in enumerate(no.args):
        if indice < len(ordem) and ordem[indice] not in kwargs:
            kwargs[ordem[indice]] = arg

    chave = _literal(kwargs.get("chave"))
    lado = _literal(kwargs.get("lado"))
    aba = _literal(kwargs.get("aba"))
    porque = _literal(kwargs.get("porque")) or ""

    afirma_no = kwargs.get("afirma")
    afirma_nome = afirma_no.id if isinstance(afirma_no, ast.Name) else None
    afirma_literal = _literal(afirma_no) if afirma_nome is None else None

    texto_no = kwargs.get("texto")
    texto_e_nao_medido = isinstance(texto_no, ast.Name) and texto_no.id == "NAO_MEDIDO"

    pendente = _le_pendencia(kwargs.get("pendente"))

    resolvel = (
        isinstance(chave, str)
        and isinstance(lado, str)
        and isinstance(aba, str)
        and isinstance(porque, str)
        and (afirma_nome is not None or isinstance(afirma_literal, str))
        and (pendente is None or "_nao_resolvel" not in pendente)
    )
    erro = None
    if not resolvel:
        erro = (
            "não consegui resolver esta `Fala` estaticamente — todo argumento "
            "tem de ser literal (string/None) ou um dos nomes conhecidos "
            "(NAO_MEDIDO, AFIRMA_*), nunca uma expressão dinâmica"
        )

    return FalaEncontrada(
        arquivo=str(caminho.relative_to(raiz)),
        linha=no.lineno,
        chave=chave if isinstance(chave, str) else None,
        lado=lado if isinstance(lado, str) else None,
        aba=aba if isinstance(aba, str) else None,
        afirma_nome=afirma_nome,
        afirma_valor=afirma_literal if isinstance(afirma_literal, str) else None,
        porque=porque if isinstance(porque, str) else "",
        texto_e_nao_medido=texto_e_nao_medido,
        pendente=pendente,
        resolvel=resolvel,
        erro_de_leitura=erro,
    )


def descobre_falas(app_dir: Path, raiz: Path) -> list[FalaEncontrada]:
    """Toda chamada `Fala(...)` em `app/**.py`, por AST — nunca por `grep`.

    A população desta função é a de `Fala` DECLARADA, e é ela que o portão
    compara contra `FATOS`. Uma frase que cita transporte e não declarou nada
    é assunto de `descobre_frases_de_transporte` (P-09), e só nas abas
    promovidas.

    CORREÇÃO DE FATO, 25/08/2026: até esta data este docstring dizia que
    "`grep` por palavra (cabo/rádio/Bluetooth) foi TENTADO e MEDIU
    falso-negativo perto de 100%". Isso trocava duas medições da
    PAREAMENTO-01. O falso-negativo de ~100% foi da régua que tentou casar as
    37 linhas fortes do mapa com o texto da tela **pela palavra do `rotulo`**
    (a direção "o mapa sabe e a tela não oferece"), e essa régua está
    descartada. A régua por palavra de transporte SOBRE O TEXTO DA TELA é
    outra coisa, e a própria sprint a publica como **piso** medido: 31 frases
    em 23/08. Recontada aqui com régua independente (AST, literal de texto
    fora de docstring, fora de `Fala(...)`, com fronteira de palavra): **38
    frases em 10 arquivos** na base de 25/08/2026 com as oito frentes da
    madrugada integradas. Ela não tem falso-negativo perto de 100%; tem
    falso-POSITIVO alto — a maioria é rótulo ou relato de estado, não
    afirmação de capacidade — e é por isso que P-09 vem com `FRASES_SEM_FALA`,
    linha a linha e com razão escrita, em vez de exigir `Fala` para todas.

    **O número acima envelhece, e por isso não é régua de nada.** Quem quiser
    o de hoje roda `--censo-de-transporte`, que o conta na árvore viva; nenhum
    portão desta casa o lê daqui.
    """
    encontradas: list[FalaEncontrada] = []
    for caminho in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in caminho.parts:
            continue
        if str(caminho.relative_to(raiz)) in _MODULOS_QUE_ESTE_PORTAO_IMPORTA:
            continue  # o registro declara os TIPOS de `Fala`, não instâncias
        try:
            fonte = caminho.read_text(encoding="utf-8")
            arvore = ast.parse(fonte, filename=str(caminho))
        except (OSError, SyntaxError) as exc:
            encontradas.append(
                FalaEncontrada(
                    arquivo=str(caminho.relative_to(raiz)),
                    linha=0,
                    chave=None,
                    lado=None,
                    aba=None,
                    afirma_nome=None,
                    afirma_valor=None,
                    porque="",
                    texto_e_nao_medido=False,
                    pendente=None,
                    resolvel=False,
                    erro_de_leitura=f"não consegui ler/parsear: {exc}",
                )
            )
            continue
        for no in ast.walk(arvore):
            if _e_chamada_de(no, "Fala"):
                assert isinstance(no, ast.Call)
                encontradas.append(_le_fala(no, caminho, raiz))
    return encontradas


def descobre_falas_da_tela(raiz: Path) -> list[FalaEncontrada]:
    """`descobre_falas` em TODA raiz de tela — é o que o `main()` usa.

    `descobre_falas(app_dir, raiz)` continua recebendo UMA pasta de propósito:
    `scripts/gerar-mapa.py` e `scripts/gerar-painel.py` a chamam assim, e uma
    troca de assinatura os quebraria em silêncio (os dois carregam este arquivo
    por `spec_from_file_location`, então nenhum portão de import os pegaria).
    Quem quiser as duas raízes chama esta.
    """
    encontradas: list[FalaEncontrada] = []
    for relativo in RAIZES_DE_TELA:
        encontradas.extend(descobre_falas(raiz / relativo, raiz))
    return encontradas


# ─────────────────────────────────────────────────────────────────────────
# A COMPARAÇÃO CONTRA `FATOS`
# ─────────────────────────────────────────────────────────────────────────


def valida(
    falas: list[FalaEncontrada],
    fatos: dict[str, dict[str, object]],
    afirma_por_nome: dict[str, str],
    causa_de_fora: frozenset[str],
) -> list[str]:
    problemas: list[str] = []
    for fala in falas:
        origem = fala.origem

        if not fala.resolvel:
            problemas.append(f"{origem}: {fala.erro_de_leitura}")
            continue

        afirma = (
            afirma_por_nome.get(fala.afirma_nome or "")
            if fala.afirma_nome
            else fala.afirma_valor
        )
        if afirma is None:
            problemas.append(
                f"{origem}: `afirma={fala.afirma_nome or fala.afirma_valor!r}` não é um "
                "AFIRMA_* conhecido — o vocabulário tem um dono só "
                "(app/fala_do_mapa.py)"
            )
            continue

        assert fala.chave is not None and fala.lado is not None
        entrada = fatos.get(fala.chave)
        if entrada is None:
            problemas.append(
                f"{origem}: a chave {fala.chave!r} não existe em FATOS "
                f"({FATOS_DO_MAPA_RELATIVO}) — `id` incorreto, ou o mapa mudou "
                "e deixou esta Fala para trás"
            )
            continue

        # A dívida de medição: se a Fala ainda promete NAO_MEDIDO mas a
        # célula já é `medido`, a pressão vira vermelho (PAREAMENTO-01,
        # "(c) resolve-se sozinha quando a medição chegar").
        lado_dict = entrada.get(fala.lado) if isinstance(entrada, dict) else None
        if fala.texto_e_nao_medido and isinstance(lado_dict, dict):
            de_onde_sei = lado_dict.get("de_onde_sei")
            if de_onde_sei == "medido":
                problemas.append(
                    f"{origem}: a medição chegou (de_onde_sei=medido) e esta "
                    f"frase ainda diz NAO_MEDIDO. Chave: {fala.chave}. Lado: "
                    f"{fala.lado}. Escreva a frase e apague `pendente=`."
                )

        if afirma == afirma_por_nome.get("AFIRMA_EXISTE"):
            existe = entrada.get("existe")
            if existe != "tem":
                problemas.append(
                    f"{origem}: AFIRMA_EXISTE em {fala.chave!r}, e o mapa hoje "
                    f"diz existe={existe!r}"
                )
        elif afirma == afirma_por_nome.get("AFIRMA_NAO_EXISTE"):
            existe = entrada.get("existe")
            if existe != "nao-tem":
                problemas.append(
                    f"{origem}: AFIRMA_NAO_EXISTE em {fala.chave!r}, e o mapa "
                    f"hoje diz existe={existe!r}"
                )
        elif afirma in (
            afirma_por_nome.get("AFIRMA_ACIONA"),
            afirma_por_nome.get("AFIRMA_PARCIAL"),
            afirma_por_nome.get("AFIRMA_NAO_ACIONA"),
        ):
            if not isinstance(lado_dict, dict):
                problemas.append(
                    f"{origem}: o lado {fala.lado!r} não existe em "
                    f"FATOS[{fala.chave!r}]"
                )
                continue
            aciona = lado_dict.get("aciona")
            por_que = lado_dict.get("por_que_nao_aciona")
            de_onde_sei = lado_dict.get("de_onde_sei")
            if afirma == afirma_por_nome.get("AFIRMA_ACIONA") and aciona != "sim":
                problemas.append(
                    f"{origem}: AFIRMA_ACIONA em {fala.chave!r}[{fala.lado}], e "
                    f"o mapa hoje diz aciona={aciona!r}, de_onde_sei="
                    f"{de_onde_sei!r}, por_que_nao_aciona={por_que!r}"
                )
            elif afirma == afirma_por_nome.get("AFIRMA_PARCIAL") and aciona != "parcial":
                problemas.append(
                    f"{origem}: AFIRMA_PARCIAL em {fala.chave!r}[{fala.lado}], e "
                    f"o mapa hoje diz aciona={aciona!r}"
                )
            elif afirma == afirma_por_nome.get("AFIRMA_NAO_ACIONA"):
                if aciona != "não":
                    problemas.append(
                        f"{origem}: AFIRMA_NAO_ACIONA em {fala.chave!r}"
                        f"[{fala.lado}], e o mapa hoje diz aciona={aciona!r}, "
                        f"de_onde_sei={de_onde_sei!r}"
                    )
                elif por_que not in causa_de_fora:
                    problemas.append(
                        f"{origem}: AFIRMA_NAO_ACIONA em {fala.chave!r}"
                        f"[{fala.lado}] com por_que_nao_aciona={por_que!r} — "
                        "causa NOSSA, não do aparelho. Use AFIRMA_NADA + "
                        "porque= em vez de culpar o aparelho pelo que é nosso"
                    )
        elif afirma == afirma_por_nome.get("AFIRMA_NADA"):
            if not fala.porque.strip() and fala.pendente is None:
                problemas.append(
                    f"{origem}: AFIRMA_NADA sem porque= nem pendente= — a tela "
                    "não pode ficar muda sem dizer por quê"
                )
    return problemas


# ─────────────────────────────────────────────────────────────────────────
# --fila
# ─────────────────────────────────────────────────────────────────────────


def monta_fila(falas: list[FalaEncontrada]) -> list[FalaEncontrada]:
    return sorted(
        (f for f in falas if f.pendente is not None and f.resolvel),
        key=lambda f: (f.chave or "", f.lado or "", f.arquivo, f.linha),
    )


def imprime_fila(fila: list[FalaEncontrada]) -> None:
    if not fila:
        print("--fila: nenhum placeholder aberto.")
        return
    print(f"--fila: {len(fila)} placeholder(s) aberto(s), do mais antigo ao mais novo:")
    for fala in sorted(fila, key=lambda f: str((f.pendente or {}).get("aberta_em", ""))):
        p = fala.pendente or {}
        print(
            f"  {fala.chave} [{fala.lado}] · aba {fala.aba} · {fala.origem} · "
            f"aberta em {p.get('aberta_em')} · prazo {p.get('prazo_dias')} dia(s) · "
            f"quem fecha: {p.get('quem_fecha')} · falta: {p.get('o_que_falta')}"
        )


# ─────────────────────────────────────────────────────────────────────────
# --exigir-prazo
# ─────────────────────────────────────────────────────────────────────────


def prazos_vencidos(falas: list[FalaEncontrada], hoje: date) -> list[tuple[FalaEncontrada, int]]:
    """`(fala, dias_de_atraso)` para cada placeholder cujo prazo já passou."""
    vencidos: list[tuple[FalaEncontrada, int]] = []
    for fala in falas:
        if fala.pendente is None or not fala.resolvel:
            continue
        aberta_em_txt = fala.pendente.get("aberta_em")
        prazo_dias = fala.pendente.get("prazo_dias")
        if not isinstance(aberta_em_txt, str) or not isinstance(prazo_dias, int):
            continue
        try:
            aberta_em = date.fromisoformat(aberta_em_txt)
        except ValueError:
            continue
        vencimento = aberta_em.toordinal() + prazo_dias
        atraso = hoje.toordinal() - vencimento
        if atraso > 0:
            vencidos.append((fala, atraso))
    return vencidos


# ─────────────────────────────────────────────────────────────────────────
# Z6-08 — o número medido tem um dono só
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class NumeroEncontrado:
    constante: str
    valor: float | None
    chave: str
    coluna: str
    arquivo: str
    linha: int


def _mapa_de_constantes_numericas(arvore: ast.Module) -> dict[str, float]:
    """`{NOME: valor}` de toda atribuição de módulo `NOME = <número literal>`.

    Cobre `Assign` (`NOME = 1.0`) e `AnnAssign` (`NOME: Final = 1.0`) — as
    duas formas que `radio_da_mesa.py` usa.
    """
    valores: dict[str, float] = {}
    for no in arvore.body:
        alvo_e_valor: tuple[ast.expr, ast.expr | None] | None = None
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            alvo_e_valor = (no.targets[0], no.value)
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvo_e_valor = (no.target, no.value)
        if alvo_e_valor is None:
            continue
        alvo, valor_no = alvo_e_valor
        if not isinstance(alvo, ast.Name):
            continue
        literal = _literal(valor_no)
        if isinstance(literal, (int, float)) and not isinstance(literal, bool):
            valores[alvo.id] = float(literal)
    return valores


def descobre_numeros(raiz: Path) -> list[NumeroEncontrado]:
    """Toda tupla de `NUMEROS_MEDIDOS_NO_MAPA` em `integrations/radio_da_mesa.py`.

    Por AST: o arquivo puxa `structlog` por `core.sysfs_leds`, e importar o
    módulo faria este portão `ImportError` num runner sem GUI/deps — o mesmo
    motivo de nunca importar `app/`.
    """
    caminho = raiz / NUMEROS_RELATIVO
    if not caminho.exists():
        return []
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte, filename=str(caminho))
    constantes = _mapa_de_constantes_numericas(arvore)

    encontrados: list[NumeroEncontrado] = []
    for no in ast.walk(arvore):
        alvo_e_valor: tuple[ast.expr, ast.expr | None] | None = None
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            alvo_e_valor = (no.targets[0], no.value)
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvo_e_valor = (no.target, no.value)
        if alvo_e_valor is None:
            continue
        alvo, valor_no = alvo_e_valor
        if not (isinstance(alvo, ast.Name) and alvo.id == "NUMEROS_MEDIDOS_NO_MAPA"):
            continue
        if not isinstance(valor_no, (ast.Tuple, ast.List)):
            continue
        for item in valor_no.elts:
            if not isinstance(item, ast.Tuple) or len(item.elts) != 4:
                continue
            nome_no, valor_ref_no, chave_no, coluna_no = item.elts
            nome = _literal(nome_no)
            chave = _literal(chave_no)
            coluna = _literal(coluna_no)
            valor: float | None = None
            if isinstance(valor_ref_no, ast.Name):
                valor = constantes.get(valor_ref_no.id)
            else:
                literal = _literal(valor_ref_no)
                if isinstance(literal, (int, float)) and not isinstance(literal, bool):
                    valor = float(literal)
            if not (isinstance(nome, str) and isinstance(chave, str) and isinstance(coluna, str)):
                continue
            encontrados.append(
                NumeroEncontrado(
                    constante=nome,
                    valor=valor,
                    chave=chave,
                    coluna=coluna,
                    arquivo=str(caminho.relative_to(raiz)),
                    linha=item.lineno,
                )
            )
    return encontrados


def _le_celulas_do_mapa(raiz: Path) -> dict[str, dict[str, str]]:
    """`{id: {coluna: valor}}` do CSV — só o que Z6-08 precisa, lido direto:
    `radio_ressalva` é PROSA (não deriva, nunca entra em `FATOS`), então esta
    checagem não pode usar `fatos_do_mapa.py`.
    """
    import csv

    caminho = raiz / MAPA_RELATIVO
    if not caminho.exists():
        return {}
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    return {linha["id"]: linha for linha in linhas if linha.get("id")}


def valida_numeros(
    numeros: list[NumeroEncontrado],
    celulas: dict[str, dict[str, str]],
    formata_pt_br: Callable[[float], str],
) -> list[str]:
    """`formata_pt_br` vem de `app/fala_do_mapa.py`, NUNCA redigitado aqui.

    A régua e a legenda têm de ser a mesma peça — é a regra que P-01 da
    PAREAMENTO-01 escreveu para o vocabulário e que vale igual para o
    FORMATO. Até 25/08/2026 esta função trazia a sua própria cópia de
    `f"{v:.1f}".replace(".", ",")`, e era a QUARTA da árvore (as outras três:
    `app/fala_do_mapa.py:228`, `app/actions/config/secao_controles.py:434` e
    `integrations/plano_de_radio.py:214`). Com a cópia, mudar
    `formata_pt_br` para duas casas deixava este portão conferindo uma casa —
    verde por cima de uma divergência entre a constante e a célula, que é
    exatamente o que ele existe para pegar.
    """
    problemas: list[str] = []
    for numero in numeros:
        origem = f"{numero.arquivo}:{numero.linha}"
        if numero.valor is None:
            problemas.append(
                f"{origem}: não consegui resolver o valor de {numero.constante!r} "
                "por AST — declare `valor=NOME_DA_CONSTANTE` (a mesma "
                "referência, nunca um literal copiado)"
            )
            continue
        linha = celulas.get(numero.chave)
        if linha is None:
            problemas.append(
                f"{origem}: a chave {numero.chave!r} não existe em {MAPA_RELATIVO}"
            )
            continue
        celula = linha.get(numero.coluna, "")
        esperado = formata_pt_br(numero.valor)
        if esperado not in celula:
            problemas.append(
                f"{origem}: {numero.constante} = {numero.valor} (formatado "
                f"{esperado!r}) não aparece em {numero.coluna} de "
                f"{numero.chave!r} ({MAPA_RELATIVO}). A constante e a célula "
                "são a MESMA medição — atualize a célula (ou a nota de "
                "porque mudou) no mesmo commit que a constante"
            )
    return problemas


# ─────────────────────────────────────────────────────────────────────────
# P-09 — O PORTÃO CRESCE DE "AVISA" PARA "REPROVA", UMA ABA POR VEZ
# ─────────────────────────────────────────────────────────────────────────
#
# Até aqui o portão só enxerga o que ALGUÉM LEMBROU de declarar: `Fala` é
# opt-in, e uma frase de transporte nova entra na tela sem nada acusar. É o
# defeito que dá título à PAREAMENTO-01 — "a medição nova tem de chegar
# SOZINHA na tela" — visto do outro lado: a tela afirma, e o mapa não fica
# sabendo.
#
# A trava é por ABA, e nunca por árvore inteira, porque a árvore inteira
# reprovaria hoje em 40 frases e seria desligada na semana seguinte (o motivo
# está escrito na PAREAMENTO-01, "onde a migração pode dar errado", e é o
# mesmo de `scripts/validar-palavra-de-tela.py`). Aba FORA de
# `ABAS_COM_FALA_DECLARADA` é livre; aba DENTRO tem de ter 100% das frases de
# transporte ou declaradas como `Fala`, ou isentas uma a uma com razão
# escrita.

#: As abas em que toda frase de tela que cita transporte tem de estar
#: declarada. **Nasce vazio de propósito** (Z6, "o que fica aberto"): no dia 1
#: o registro tem uma `Fala` só, e promover uma aba agora exigiria editar
#: arquivos de outras frentes.
#:
#: **O conjunto SÓ CRESCE.** Quem trava isso é
#: `tests/unit/test_abas_promovidas_so_crescem_p09.py`, e o conjunto de
#: referência dele é literal DO PRÓPRIO ARQUIVO DE TESTE — nunca lido daqui.
#: Um teto lido da própria fonte passa sempre, e é o defeito que a ADR-016
#: pagou por um mês (a lição está em
#: `tests/unit/test_o_mapa_separa_divida_de_decisao.py`).
#:
#: As duas primeiras a promover, quando as abas tiverem dono livre: **Início**
#: e **Status** — é onde morava a frase falsa de 17/08 e onde a pessoa lê
#: "isto funciona?".
ABAS_COM_FALA_DECLARADA: frozenset[str] = frozenset()

#: Quais arquivos desenham cada aba promovida, relativos a uma raiz de tela
#: (`RAIZES_DE_TELA` — `app/` ou `interface/`, procuradas nessa ordem por
#: `_caminho_da_aba`). Só é preciso declarar a aba que foi promovida: aba livre
#: não precisa de linha aqui.
#:
#: É mapa escrito à mão, e isso é uma escolha: o produto identifica aba pelo
#: **id do Glade** (`app/app.py::_REFRESH_POR_ABA`, chaves `tab_home_box` e
#: companhia) e `Fala.aba` fala o nome que a pessoa lê ("Início"). Não há hoje
#: nenhuma peça que case os dois, e inventar uma casaria por heurística o que
#: precisa ser declarado.
#:
#: Aba promovida SEM linha aqui **reprova alto** — nunca passa calada. Um
#: portão que se desliga por omissão de configuração é a forma silenciosa de
#: portão nenhum (a mesma razão escrita em `anonymity-check.yml:67-70`).
ARQUIVOS_DA_ABA: dict[str, tuple[str, ...]] = {}

#: As frases de aba promovida que citam transporte e NÃO precisam de `Fala`,
#: uma a uma, com a razão escrita. Chaveada pelo TEXTO EXATO, no molde de
#: `DIVIDA_DA_PALAVRA_01` de `scripts/validar-palavra-de-tela.py`: mexer no
#: texto derruba a isenção e obriga a rejustificá-la, que é o que se quer.
#:
#: **Entrada que não casa mais com nenhuma frase de aba promovida REPROVA.**
#: Lápide que sobrevive à própria cura é o defeito que este tipo de lista
#: existe para matar — medido em 25/08/2026 no
#: `portao_a_casa_sabe_e_o_produto_nao_faz`, onde duas notas datadas seguiram
#: dizendo "nada de produção chama" sobre funções que a produção passou a
#: chamar.
FRASES_SEM_FALA: dict[str, str] = {}

#: As palavras que fazem uma frase "citar transporte". Casadas com fronteira
#: de palavra: sem ela, `cabo` casa dentro de `acabou`.
#:
#: `usb` entra e engorda a lista de propósito — no cabo o transporte É USB, e
#: uma régua que o deixasse de fora perderia "pelo barramento USB". O preço é
#: falso-positivo, e o preço é pago pela `FRASES_SEM_FALA`, que é declarada e
#: envelhece; o preço do contrário seria falso-negativo, que é mudo.
PALAVRAS_DE_TRANSPORTE: frozenset[str] = frozenset(
    {"cabo", "cabos", "rádio", "rádios", "bluetooth", "usb", "sem fio", "sem-fio"}
)

#: A blindagem declarada da régua, para ninguém a ler como censo completo:
#: literal curto ou sem espaço fica de fora (é identificador, chave de
#: dicionário, fragmento de formatação), e f-string montada em tempo de
#: execução também — o `ast.JoinedStr` só entrega os pedaços literais.
_MINIMO_DE_FRASE = 12

_TRANSPORTE = re.compile(
    "(?<!\\w)(" + "|".join(sorted(map(re.escape, PALAVRAS_DE_TRANSPORTE))) + ")(?!\\w)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FraseDeTransporte:
    arquivo: str
    linha: int
    texto: str

    @property
    def origem(self) -> str:
        return f"{self.arquivo}:{self.linha}"


def _nos_de_docstring(arvore: ast.Module) -> set[int]:
    """`id()` de cada `ast.Constant` que é docstring de módulo/função/classe.

    Docstring é prosa para quem lê o código, não fala de tela — contá-la
    levaria o censo de 40 para bem mais de cem (a PAREAMENTO-01 mediu 31 de
    piso e 135 de teto justamente por causa disto).
    """
    fora: set[int] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        corpo = getattr(no, "body", [])
        if not corpo:
            continue
        primeiro = corpo[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            fora.add(id(primeiro.value))
    return fora


def _nos_dentro_de_fala(arvore: ast.Module) -> set[int]:
    """`id()` de cada `ast.Constant` que mora DENTRO de uma chamada `Fala(...)`.

    É o que faz declarar uma `Fala` resolver a reprovação: o texto sai da
    população de "frase não declarada" por estar onde deveria estar.
    """
    dentro: set[int] = set()
    for no in ast.walk(arvore):
        if not _e_chamada_de(no, "Fala"):
            continue
        for filho in ast.walk(no):
            if isinstance(filho, ast.Constant):
                dentro.add(id(filho))
    return dentro


def frases_de_um_arquivo(caminho: Path, raiz: Path) -> list[FraseDeTransporte]:
    """As frases de tela deste arquivo que citam transporte."""
    try:
        fonte = caminho.read_text(encoding="utf-8")
        arvore = ast.parse(fonte, filename=str(caminho))
    except (OSError, SyntaxError):
        return []
    fora = _nos_de_docstring(arvore) | _nos_dentro_de_fala(arvore)
    achadas: list[FraseDeTransporte] = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Constant) and isinstance(no.value, str)):
            continue
        if id(no) in fora:
            continue
        texto = no.value
        if len(texto) < _MINIMO_DE_FRASE or " " not in texto:
            continue
        if not _TRANSPORTE.search(texto):
            continue
        achadas.append(
            FraseDeTransporte(
                arquivo=str(caminho.relative_to(raiz)), linha=no.lineno, texto=texto
            )
        )
    return sorted(achadas, key=lambda f: (f.arquivo, f.linha))


def descobre_frases_de_transporte(app_dir: Path, raiz: Path) -> list[FraseDeTransporte]:
    """O censo de UMA raiz de tela. Para as duas, `descobre_frases_da_tela`."""
    achadas: list[FraseDeTransporte] = []
    for caminho in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in caminho.parts:
            continue
        if str(caminho.relative_to(raiz)) in _MODULOS_QUE_ESTE_PORTAO_IMPORTA:
            continue  # o registro declara TIPOS, não frase de tela
        achadas.extend(frases_de_um_arquivo(caminho, raiz))
    return achadas


def descobre_frases_da_tela(raiz: Path) -> list[FraseDeTransporte]:
    """O censo inteiro — TODA raiz de tela, que é o que `--censo-de-transporte`
    imprime desde 06/09/2026. Antes disso ele imprimia só `app/`, e publicava
    como "o censo" um número que deixava de fora a maior parte da tela.
    """
    achadas: list[FraseDeTransporte] = []
    for relativo in RAIZES_DE_TELA:
        achadas.extend(descobre_frases_de_transporte(raiz / relativo, raiz))
    return achadas


def _caminho_da_aba(raiz: Path, relativo: str) -> Path | None:
    """O arquivo de uma aba promovida, procurado em TODA raiz de tela.

    `ARQUIVOS_DA_ABA` guarda o caminho relativo à raiz de tela, sem dizer qual
    — a aba Início pode morar em `app/` hoje e em `interface/` amanhã, e o
    portão não pode virar vermelho por causa de uma mudança de casa que não
    mudou uma palavra da tela. Achar em NENHUMA das duas continua reprovando.
    """
    for base in RAIZES_DE_TELA:
        caminho = raiz / base / relativo
        if caminho.is_file():
            return caminho
    return None


def valida_abas_promovidas(raiz: Path) -> list[str]:
    """Toda frase de transporte de aba promovida está declarada ou isenta?"""
    problemas: list[str] = []
    vistas: list[FraseDeTransporte] = []

    for aba in sorted(ABAS_COM_FALA_DECLARADA):
        arquivos = ARQUIVOS_DA_ABA.get(aba)
        if not arquivos:
            problemas.append(
                f"a aba {aba!r} está em ABAS_COM_FALA_DECLARADA e não tem linha "
                "em ARQUIVOS_DA_ABA — promover sem dizer quais arquivos são da "
                "aba desliga a trava em silêncio. Declare os arquivos ou tire a "
                "aba do conjunto"
            )
            continue
        for relativo in arquivos:
            caminho = _caminho_da_aba(raiz, relativo)
            if caminho is None:
                problemas.append(
                    f"ARQUIVOS_DA_ABA[{aba!r}] cita {relativo!r}, que não existe "
                    f"em nenhuma raiz de tela ({', '.join(RAIZES_DE_TELA)}) — o "
                    "arquivo foi renomeado ou apagado, e a aba ficou sem "
                    "cobertura sem ninguém notar"
                )
                continue
            for frase in frases_de_um_arquivo(caminho, raiz):
                vistas.append(frase)
                razao = FRASES_SEM_FALA.get(frase.texto)
                if razao is not None and razao.strip():
                    continue
                if razao is not None:
                    problemas.append(
                        f"{frase.origem}: a isenção desta frase está em "
                        "FRASES_SEM_FALA com razão VAZIA — isenção sem razão "
                        "escrita é a mesma coisa que não ter portão"
                    )
                    continue
                problemas.append(
                    f"{frase.origem}: a aba {aba!r} está promovida e esta frase "
                    f"cita transporte sem declarar de que célula do mapa fala: "
                    f"{frase.texto[:90]!r}. Declare uma `Fala` (chave, lado, "
                    "afirma) ou ponha o texto em FRASES_SEM_FALA com a razão"
                )

    textos_vistos = {f.texto for f in vistas}
    for texto, razao in FRASES_SEM_FALA.items():
        if texto not in textos_vistos:
            problemas.append(
                f"FRASES_SEM_FALA tem entrada que não casa com frase nenhuma de "
                f"aba promovida: {texto[:90]!r}. A frase mudou ou sumiu — APAGUE "
                "a entrada. Lápide que sobrevive à própria cura é o que esta "
                "lista existe para matar"
            )
        elif not razao.strip():
            problemas.append(
                f"FRASES_SEM_FALA[{texto[:60]!r}] está sem razão escrita."
            )
    return problemas


# ─────────────────────────────────────────────────────────────────────────
# O PISO — o "quase não mediu" para de ser só aviso
# ─────────────────────────────────────────────────────────────────────────
#
# 06/09/2026. Até aqui o `main()` terminava com `rc=0` imprimindo *"A RÉGUA
# QUASE NÃO MEDIU: 1 `Fala` declarada(s), … contra as 308 célula(s)"*. É a
# forma que a casa nomeou em 04/09/2026: **o instrumento sabe do próprio risco
# e AVISA em vez de RESOLVER — aviso no cabeçalho de um comando que termina
# verde ninguém lê.**
#
# O que o piso resolve, e é só isto: o conjunto que a régua mede **não pode
# encolher**. Hoje ele vale exatamente o que está declarado, então o `rc`
# continua 0 — o verde de hoje é o piso, não uma promessa. Amanhã, apagar a
# única `Fala` do produto, tirar um número medido, despromover uma aba ou
# encurtar `RAIZES_DE_TELA` reprova, nomeando o piso e o achado.
#
# O QUE O PISO NÃO É: veto de frase de tela. Palavra dela, 06/09/2026, sobre o
# mapa: *"Esse mapa é funcional e real. tá desatualizado no sentido de não ter
# sido medido. foi e tudo funciona."* Uma célula atrasada é medição que ninguém
# escreveu de volta, não aparelho que não funciona — e uma régua que reprovasse
# a tela por causa disso transformaria mapa atrasado em freio. Esta régua
# INFORMA, conta e cobra declaração; ela não reprova frase por causa de célula
# atrasada.  <!-- noqa-acento: citação literal dela -->
#
# **NUNCA baixe este piso para ficar verde.** Se ele reprovou, descubra o que
# encolheu — é a mesma regra escrita em `test_o_mapa_nunca_encolhe.py`.

#: O piso, MEDIDO em 06/09/2026 nesta árvore (não digitado): `--all` contava
#: `1 Fala declarada(s), 3 número(s) de tela e 0 aba(s) promovida(s)`, com as
#: duas raízes de `RAIZES_DE_TELA`. `abas` nasce em 0 porque promover uma aba
#: hoje exigiria editar arquivos de outras frentes — e um piso de zero ainda
#: vale, porque é ele que faz a PRIMEIRA promoção virar irreversível.
#:
#: O conjunto SÓ CRESCE, e crescer PASSA: quem promover uma aba não precisa
#: tocar aqui. Régua que reprova quem melhora é o defeito que onze réguas
#: desta casa já tiveram, todas pela mesma forma — digitavam o que deviam ler.
#:
#: A catraca deste número é literal DO ARQUIVO DE TESTE
#: (`tests/unit/test_a_fala_de_tela_alcanca_a_interface_nova.py`), nunca lido
#: daqui: um teto lido da própria fonte passa sempre.
PISO_DA_REGUA: dict[str, int] = {"raizes": 2, "falas": 1, "numeros": 3, "abas": 0}

#: O que cada chave de `PISO_DA_REGUA` mede, para a mensagem de erro dizer ao
#: leitor o que encolheu sem ele precisar abrir este arquivo.
_O_QUE_O_PISO_MEDE: dict[str, str] = {
    "raizes": "raiz(es) de tela varrida(s) (`RAIZES_DE_TELA`)",
    "falas": "`Fala` declarada(s) na tela",
    "numeros": "número(s) medido(s) que a tela mostra (`NUMEROS_MEDIDOS_NO_MAPA`)",
    "abas": "aba(s) promovida(s) (`ABAS_COM_FALA_DECLARADA`)",
}


def e_a_arvore_do_produto(raiz: Path) -> tuple[bool, str]:
    """`(é o produto?, por que não)` — o piso vale para o produto, e só.

    As árvores de mentira da suíte montam três arquivos num `tmp_path` para
    exercer UMA regra; cobrar delas o piso do produto seria cobrar de um
    instrumento de teste o tamanho da casa inteira. A pergunta tem de ser
    respondida por coisa que exista no disco, nunca por um caminho gravado —
    a árvore do produto viaja (`git worktree`), e uma régua presa a
    `/mnt/…/hefesto-dualsense4unix` mediria a árvore de outra pessoa.

    E ela NUNCA se desliga calada: quando devolve `False`, o `main()` imprime
    a razão. Um portão que se desliga por omissão é a forma silenciosa de
    portão nenhum (a mesma razão escrita em `anonymity-check.yml:67-70`).
    """
    if not (raiz / MAPA_RELATIVO).is_file():
        return False, f"não há {MAPA_RELATIVO} nesta árvore"
    faltando = [relativo for relativo in RAIZES_DE_TELA if not (raiz / relativo).is_dir()]
    if faltando:
        return False, "não há a(s) raiz(es) de tela " + ", ".join(faltando)
    return True, ""


def valida_piso_da_regua(medido: dict[str, int], piso: dict[str, int]) -> list[str]:
    """O conjunto medido hoje contra o piso. Pura de propósito.

    É o miolo do veredito, e o teste a exerce com números sintéticos — sem
    isso ela poderia estar acertando por ter a resposta escrita, e não por
    comparar (é o molde de `tem_lastro_nos_dois`, em
    `test_a_aba_emulacao_nao_promete_transporte_sem_lastro.py`).
    """
    problemas: list[str] = []
    for nome in sorted(piso):
        agora = medido.get(nome, 0)
        if agora >= piso[nome]:
            continue
        problemas.append(
            f"{nome}: a régua mede {agora} e o piso é {piso[nome]} — "
            f"{_O_QUE_O_PISO_MEDE.get(nome, nome)}. A régua ENCOLHEU: alguém "
            "apagou, renomeou ou despromoveu o que ela enxergava. NÃO baixe o "
            "piso para ficar verde — descubra o que encolheu"
        )
    return problemas


# ─────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--all", action="store_true", help="roda todas as checagens (o modo do CI)")
    modo.add_argument("--fila", action="store_true", help="lista os placeholders abertos")
    modo.add_argument(
        "--exigir-prazo",
        action="store_true",
        help="como --all, mas prazo vencido é FALHA (o modo do release)",
    )
    modo.add_argument(
        "--censo-de-transporte",
        action="store_true",
        help="imprime as frases de tela que citam transporte (sempre sai 0)",
    )
    parser.add_argument("--raiz", type=Path, default=RAIZ)
    parser.add_argument("--hoje", type=str, default=None, help="AAAA-MM-DD, só para teste")
    args = parser.parse_args(argv)

    raiz = args.raiz.resolve()
    hoje = date.fromisoformat(args.hoje) if args.hoje else date.today()

    fala_do_mapa, fatos_do_mapa = carrega_registro(raiz)
    afirma_por_nome = {
        nome: getattr(fala_do_mapa, nome)
        for nome in dir(fala_do_mapa)
        if nome.startswith("AFIRMA_")
    }
    causa_de_fora = frozenset(fala_do_mapa.CAUSA_DE_FORA)
    fatos = dict(fatos_do_mapa.FATOS)

    falas = descobre_falas_da_tela(raiz)

    if args.fila:
        imprime_fila(monta_fila(falas))
        return 0

    if args.censo_de_transporte:
        frases = descobre_frases_da_tela(raiz)
        arquivos = len({f.arquivo for f in frases})
        for frase in frases:
            print(f"{frase.origem}: {frase.texto}")
        print("")
        for relativo in RAIZES_DE_TELA:
            desta = [f for f in frases if f.arquivo.startswith(f"{relativo}/")]
            print(
                f"  {relativo}: {len(desta)} frase(s) em "
                f"{len({f.arquivo for f in desta})} arquivo(s)."
            )
        print(f"\n{len(frases)} frase(s) de transporte em {arquivos} arquivo(s).")
        return 0

    problemas = valida(falas, fatos, afirma_por_nome, causa_de_fora)
    numeros = descobre_numeros(raiz)
    problemas.extend(
        valida_numeros(numeros, _le_celulas_do_mapa(raiz), fala_do_mapa.formata_pt_br)
    )
    problemas.extend(valida_abas_promovidas(raiz))
    vencidos = prazos_vencidos(falas, hoje)

    medido = {
        "raizes": len(RAIZES_DE_TELA),
        "falas": len(falas),
        "numeros": len(numeros),
        "abas": len(ABAS_COM_FALA_DECLARADA),
    }
    e_o_produto, por_que_nao = e_a_arvore_do_produto(raiz)
    encolheu = valida_piso_da_regua(medido, PISO_DA_REGUA) if e_o_produto else []

    if vencidos:
        rotulo = "FALHA" if args.exigir_prazo else "AVISO"
        print(f"{rotulo}: {len(vencidos)} placeholder(s) com prazo vencido:")
        for fala, atraso in vencidos:
            p = fala.pendente or {}
            print(
                f"  {fala.origem}: {fala.chave} [{fala.lado}] venceu há {atraso} "
                f"dia(s) — quem fecha: {p.get('quem_fecha')}"
            )
        if args.exigir_prazo:
            problemas.extend(
                f"{fala.origem}: prazo vencido há {atraso} dia(s)" for fala, atraso in vencidos
            )
        print("")

    if encolheu:
        print(f"FALHA: a régua ENCOLHEU em {len(encolheu)} ponto(s):")
        for problema in encolheu:
            print(f"  {problema}")
        print("")

    if problemas:
        print(f"FALHA: {len(problemas)} desacordo(s) entre a tela e o mapa:")
        for problema in problemas:
            print(f"  {problema}")

    if encolheu or problemas:
        return 1

    if not e_o_produto:
        print(
            f"PISO NÃO APLICADO: {por_que_nao} — esta árvore não é o produto, "
            "e o piso de `PISO_DA_REGUA` só vale para ele."
        )

    # O TAMANHO DO CONJUNTO MEDIDO VAI NA FRASE DE SUCESSO — 26/08/2026
    # (LEVA-4-E). Até aqui esta linha dizia só `OK: 1 Fala declarada(s)`, e
    # quem lia o verde do `portoes.sh` não tinha como saber que o produto
    # inteiro tem UMA `Fala` (`app/widgets/external_card.py`) contra um mapa de
    # 308 células. Com um conjunto desse tamanho, "nenhum desacordo" não é
    # prova de acordo — é a régua confundindo a PALAVRA com o ATO, que é o
    # padrão que a casa nomeou em 25/08. `rc` continua 0 de propósito: o
    # tamanho do conjunto é decisão de produto (quantas abas foram promovidas),
    # e portão não reprova ninguém por uma fila que ele não enche.
    #
    # O QUE MUDOU EM 06/09/2026: o tamanho de hoje virou PISO. Não encher a
    # fila continua verde; ESVAZIÁ-LA, não. A frase abaixo diz o piso junto do
    # tamanho, para quem lê o verde saber contra o que ele está sendo medido.
    piso = ", ".join(f"{nome}≥{valor}" for nome, valor in sorted(PISO_DA_REGUA.items()))
    tamanho = (
        f"{len(falas)} `Fala` declarada(s), {len(numeros)} número(s) de tela e "
        f"{len(ABAS_COM_FALA_DECLARADA)} aba(s) promovida(s), contra as "
        f"{len(fatos)} célula(s) de {FATOS_DO_MAPA_RELATIVO}, varrendo "
        f"{len(RAIZES_DE_TELA)} raiz(es) de tela ({', '.join(RAIZES_DE_TELA)})"
    )
    if len(falas) <= 1:
        print(
            f"A RÉGUA QUASE NÃO MEDIU: {tamanho}. Um conjunto deste tamanho "
            "não distingue uma tela em acordo com o mapa de uma tela que "
            "simplesmente não declara nada — promova mais abas em "
            f"`ABAS_COM_FALA_DECLARADA` e o verde daqui passa a valer. É O "
            f"PISO ({piso}): abaixo dele, `rc=1`."
        )
        return 0
    print(f"OK: {tamanho}, todas de acordo. Piso: {piso}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
