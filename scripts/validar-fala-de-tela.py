#!/usr/bin/env python3
"""validar-fala-de-tela.py — o portão, nos dois sentidos."""
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

#: errada."*  <!-- noqa-acento: citação literal dela -->
RAIZES_DE_TELA: tuple[str, ...] = (APP_RELATIVO, INTERFACE_RELATIVO)

NUMEROS_RELATIVO = "src/hefesto_dualsense4unix/integrations/radio_da_mesa.py"

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
    """Toda chamada `Fala(...)` em `app/**.py`, por AST — nunca por `grep`."""
    encontradas: list[FalaEncontrada] = []
    for caminho in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in caminho.parts:
            continue
        if str(caminho.relative_to(raiz)) in _MODULOS_QUE_ESTE_PORTAO_IMPORTA:
            continue
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
    """`descobre_falas` em TODA raiz de tela — é o que o `main()` usa."""
    encontradas: list[FalaEncontrada] = []
    for relativo in RAIZES_DE_TELA:
        encontradas.extend(descobre_falas(raiz / relativo, raiz))
    return encontradas


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


@dataclass
class NumeroEncontrado:
    constante: str
    valor: float | None
    chave: str
    coluna: str
    arquivo: str
    linha: int


def _mapa_de_constantes_numericas(arvore: ast.Module) -> dict[str, float]:
    """`{NOME: valor}` de toda atribuição de módulo `NOME = <número literal>`."""
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


CAMPOS_DO_NUMERO: tuple[str, ...] = ("constante", "valor", "chave", "coluna")


def _campos_do_numero(item: ast.expr) -> tuple[ast.expr, ast.expr, ast.expr, ast.expr] | None:
    """Os quatro campos de um item da tupla, se ele for um `Numero(...)`."""
    if not _e_chamada_de(item, "Numero"):
        return None
    assert isinstance(item, ast.Call)
    if len(item.args) > len(CAMPOS_DO_NUMERO):
        return None
    campos: dict[str, ast.expr] = dict(zip(CAMPOS_DO_NUMERO, item.args, strict=False))
    for palavra in item.keywords:
        if palavra.arg not in CAMPOS_DO_NUMERO or palavra.arg in campos:
            return None
        campos[palavra.arg] = palavra.value
    if set(campos) != set(CAMPOS_DO_NUMERO):
        return None
    return (campos["constante"], campos["valor"], campos["chave"], campos["coluna"])


def descobre_numeros(raiz: Path) -> list[NumeroEncontrado]:
    """Todo `Numero(...)` de `NUMEROS_MEDIDOS_NO_MAPA` em `integrations/radio_da_mesa.py`."""
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
            campos = _campos_do_numero(item)
            if campos is None:
                continue
            nome_no, valor_ref_no, chave_no, coluna_no = campos
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
    """`{id: {coluna: valor}}` do CSV — só o que Z6-08 precisa, lido direto:"""
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
    """`formata_pt_br` vem de `app/fala_do_mapa.py`, NUNCA redigitado aqui."""
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


ABAS_COM_FALA_DECLARADA: frozenset[str] = frozenset()

ARQUIVOS_DA_ABA: dict[str, tuple[str, ...]] = {}

#: `portao_a_casa_sabe_e_o_produto_nao_faz`, onde duas notas datadas seguiram
FRASES_SEM_FALA: dict[str, str] = {}

PALAVRAS_DE_TRANSPORTE: frozenset[str] = frozenset(
    {"cabo", "cabos", "rádio", "rádios", "bluetooth", "usb", "sem fio", "sem-fio"}
)

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
    """`id()` de cada `ast.Constant` que é docstring de módulo/função/classe."""
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
    """`id()` de cada `ast.Constant` que mora DENTRO de uma chamada `Fala(...)`."""
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
            continue
        achadas.extend(frases_de_um_arquivo(caminho, raiz))
    return achadas


def descobre_frases_da_tela(raiz: Path) -> list[FraseDeTransporte]:
    """O censo inteiro — TODA raiz de tela, que é o que `--censo-de-transporte`"""
    achadas: list[FraseDeTransporte] = []
    for relativo in RAIZES_DE_TELA:
        achadas.extend(descobre_frases_de_transporte(raiz / relativo, raiz))
    return achadas


def _caminho_da_aba(raiz: Path, relativo: str) -> Path | None:
    """O arquivo de uma aba promovida, procurado em TODA raiz de tela."""
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


# atrasada.  <!-- noqa-acento: citação literal dela -->

PISO_DA_REGUA: dict[str, int] = {"raizes": 2, "falas": 1, "numeros": 3, "abas": 0}

_O_QUE_O_PISO_MEDE: dict[str, str] = {
    "raizes": "raiz(es) de tela varrida(s) (`RAIZES_DE_TELA`)",
    "falas": "`Fala` declarada(s) na tela",
    "numeros": "número(s) medido(s) que a tela mostra (`NUMEROS_MEDIDOS_NO_MAPA`)",
    "abas": "aba(s) promovida(s) (`ABAS_COM_FALA_DECLARADA`)",
}


def e_a_arvore_do_produto(raiz: Path) -> tuple[bool, str]:
    """`(é o produto?, por que não)` — o piso vale para o produto, e só."""
    if not (raiz / MAPA_RELATIVO).is_file():
        return False, f"não há {MAPA_RELATIVO} nesta árvore"
    faltando = [relativo for relativo in RAIZES_DE_TELA if not (raiz / relativo).is_dir()]
    if faltando:
        return False, "não há a(s) raiz(es) de tela " + ", ".join(faltando)
    return True, ""


def valida_piso_da_regua(medido: dict[str, int], piso: dict[str, int]) -> list[str]:
    """O conjunto medido hoje contra o piso. Pura de propósito."""
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
