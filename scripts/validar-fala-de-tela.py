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
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parent.parent
APP_RELATIVO = "src/hefesto_dualsense4unix/app"
APP = RAIZ / APP_RELATIVO
FALA_DO_MAPA_RELATIVO = f"{APP_RELATIVO}/fala_do_mapa.py"
FATOS_DO_MAPA_RELATIVO = f"{APP_RELATIVO}/fatos_do_mapa.py"
MAPA_RELATIVO = "docs/data/mapa-controles.csv"

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

    `grep` por palavra (cabo/rádio/Bluetooth) foi TENTADO e MEDIU
    falso-negativo perto de 100% (PAREAMENTO-01, "O QUE JÁ ESTÁ MEDIDO"). A
    população que importa é a de `Fala` DECLARADA, não a de frase que cita
    transporte — essa é a fronteira que faz este portão crescer sem gritar
    falso (ver Z6-10).
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
            afirma_por_nome.get(fala.afirma_nome or "", None)
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


def valida_numeros(numeros: list[NumeroEncontrado], celulas: dict[str, dict[str, str]]) -> list[str]:
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
        esperado = f"{numero.valor:.1f}".replace(".", ",")
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

    falas = descobre_falas(raiz / APP_RELATIVO, raiz)

    if args.fila:
        imprime_fila(monta_fila(falas))
        return 0

    problemas = valida(falas, fatos, afirma_por_nome, causa_de_fora)
    problemas.extend(valida_numeros(descobre_numeros(raiz), _le_celulas_do_mapa(raiz)))
    vencidos = prazos_vencidos(falas, hoje)

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

    if problemas:
        print(f"FALHA: {len(problemas)} `Fala` em desacordo com o mapa:")
        for problema in problemas:
            print(f"  {problema}")
        return 1

    print(f"OK: {len(falas)} `Fala` declarada(s), todas de acordo com {FATOS_DO_MAPA_RELATIVO}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
