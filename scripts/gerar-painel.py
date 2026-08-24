#!/usr/bin/env python3
"""gerar-painel.py — constrói painel.html: o estado do projeto, medido agora.

O IRMÃO DO specs.html
---------------------
O ``specs.html`` responde *"o que o aparelho entende, por qual canal"*. Este
responde *"onde o projeto está, e o que falta para a 0.999"*. Os dois dividem a
paleta (``scripts/paleta_da_casa.py``) e a regra que a originou: **autocontido,
zero rede, zero CDN, zero fonte web**. Abre com duplo clique.

Os números do mapa de canais que aparecem aqui NÃO são recontados: este script
importa as funções do próprio ``gerar-mapa.py``. Se os dois discordassem, um dos
dois estaria mentindo — e a casa já pagou caro por régua que mente.

RÁPIDO x CARO, E POR QUE A SEPARAÇÃO É O CORAÇÃO DESTE ARQUIVO
--------------------------------------------------------------
Um painel que só é honesto quando alguém espera sete minutos não é usado, e um
painel que finge saber o que não mediu é pior que nenhum. Então:

- **RÁPIDO** (< 2 s, roda toda vez): censo de sprints, o CSV, o SPRINT_ORDER, o
  estado do git, o tamanho da árvore. É o que o gancho de pré-commit atualiza.
- **CARO** (minutos): a suíte, o ``mypy``, os portões pesados. Ficam num cache
  (``docs/data/painel-cache.json``) com o carimbo de QUANDO foram medidos, e a
  página mostra a idade. Passou do teto, o número aparece **apagado e datado**,
  nunca como se fosse de agora.

É a mesma disciplina do resto da casa: ausência de medição se declara, não se
preenche com zero. O ``--completo`` roda os caros e atualiza o cache.

Uso:
    python3 scripts/gerar-painel.py             # só o rápido; usa o cache do caro
    python3 scripts/gerar-painel.py --completo  # roda os caros e regrava o cache
    python3 scripts/gerar-painel.py --check     # o publicado bate com as fontes?
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from paleta_da_casa import TOKENS

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "painel.html"
CACHE = RAIZ / "docs" / "data" / "painel-cache.json"
SPRINTS = RAIZ / "docs" / "process" / "sprints"
DECISOES = RAIZ / "docs" / "data" / "decisoes-dela.csv"
ORDEM = RAIZ / "docs" / "process" / "SPRINT_ORDER.md"

#: Depois de quantas horas um número caro deixa de ser "de agora".
#: Seis horas é uma sessão de trabalho: dentro dela, o número ainda descreve a
#: árvore; fora, provavelmente não.
TETO_DE_FRESCOR_H = 6.0

#: Os portões da casa que o `--completo` roda. O comando é o EXATO do CI —
#: a regra `ruff check .` != `ruff check src/ tests/` está no CLAUDE.md e já
#: custou uma leva.
PORTOES: tuple[tuple[str, list[str]], ...] = (
    ("ruff", [".venv/bin/ruff", "check", "src/", "tests/"]),
    ("mypy", [".venv/bin/mypy", "src/hefesto_dualsense4unix"]),
    ("acentuação", ["python3", "scripts/validar-acentuacao.py", "--all"]),
    ("glifos", ["python3", "scripts/validar-glifos.py", "--all"]),
    ("referências", ["python3", "scripts/validar-referencias-docs.py", "--all"]),
    ("palavra de tela", ["python3", "scripts/validar-palavra-de-tela.py", "--all"]),
    ("anonimato", ["bash", "scripts/check_anonymity.sh"]),
    ("versão", [".venv/bin/python", "scripts/check_version_consistency.py"]),
    ("empacotamento", ["bash", "scripts/check_packaging_parity.sh"]),
    ("dados de teste", ["bash", "scripts/check_test_data.sh"]),
    ("paridade de transporte", ["python3", "scripts/check_paridade_transporte.py"]),
    ("specs.html em dia", ["python3", "scripts/gerar-mapa.py", "--check"]),
)


# --- o RÁPIDO ---------------------------------------------------------------


def _texto(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def censo_de_sprints() -> dict:
    """Quantas sprints há, e quantas dizem estar abertas.

    A RÉGUA É DECLARADA, e ela é frouxa de propósito. O `SPRINT_ORDER.md`
    registra que seis sprints têm cabeçalho de concluída ACIMA de um
    `Status: ABERTA` preservado de propósito, e que três alarmes de órfã aberta
    eram da régua e não da árvore. Um classificador automático que fingisse
    resolver isso produziria número convincente e falso — que é a armadilha mais
    cara desta casa.

    Então este censo conta o que dá para contar sem julgar: arquivos, e quantos
    carregam a palavra. O julgamento é do batedor de sprints, não daqui, e a
    página diz isso com todas as letras.
    """
    arquivos = sorted(SPRINTS.rglob("*.md"))
    diz_aberta = diz_concluida = indice = 0
    for f in arquivos:
        alto = _texto(f)[:2400].upper()
        if "INDICE" in f.name.upper() or "ÍNDICE" in alto[:200]:
            indice += 1
            continue
        if re.search(r"\bABERTA\b", alto):
            diz_aberta += 1
        if re.search(r"CONCLU[IÍ]DA|FECHADA", alto):
            diz_concluida += 1
    citadas = len(set(re.findall(r"(\d{4}-\d{2}-\d{2}-[A-Za-zÀ-ÿ0-9\-]+)", _texto(ORDEM))))
    return {
        "arquivos": len(arquivos),
        "diz_aberta": diz_aberta,
        "diz_concluida": diz_concluida,
        "indices": indice,
        "citadas_na_fila": citadas,
        "fora_da_fila": max(0, len(arquivos) - indice - citadas),
    }


def decisoes_dela() -> list[dict]:
    """As decisões que esperam a palavra dela, da fonte única.

    NASCEU DE UMA OBSERVAÇÃO DELA, em 23/08/2026. Foi dito que o padrão mais
    caro do dia não era técnico: *as melhores decisões dela são as que ela toma
    VENDO, e havia decisões paradas por não terem tela*. A resposta dela:
    *"talvez encabeçar isso na nossa specs pra eu ir vendo junto contigo."*

    Por isso esta seção nasce no TOPO do painel, e por isso ela mostra o preço
    do outro lado ao lado da recomendação: decidir vendo exige ver o custo, não
    só a pergunta.

    A fonte é `docs/data/decisoes-dela.csv`, no molde do mapa de canais — um
    arquivo, editável à mão ou pela bancada, e o artefato deriva. Decisão
    respondida NÃO some: ela ganha `escolha` e `decidida_em`, e passa a
    aparecer no rodapé da seção. É a regra da casa — decisão medida não se
    apaga.
    """
    try:
        with DECISOES.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except (OSError, ValueError):
        return []


def numeros_do_mapa() -> dict:
    """Os números do mapa de canais, vindos do PRÓPRIO gerador do specs.html.

    Importar em vez de reimplementar é o que torna a sincronia verdadeira: se
    este painel recontasse, ele poderia discordar da página irmã, e a casa
    ficaria com duas verdades sobre o mesmo CSV.
    """
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "gerar_mapa", RAIZ / "scripts" / "gerar-mapa.py"
        )
        if spec is None or spec.loader is None:
            return {"erro": "não consegui carregar o gerar-mapa.py"}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        linhas = mod.le_csv()
        sem_teste = sum(1 for lin in linhas if not (lin.get("teste_que_morde") or "").strip())
        return {
            "linhas": len(linhas),
            "chaves": len({lin["chave"] for lin in linhas}),
            "assimetrias": mod.assimetrias(linhas),
            "sem_teste": sem_teste,
        }
    except Exception as exc:  # o painel nunca pode morrer por causa de uma fonte
        return {"erro": f"{type(exc).__name__}: {exc}"}


def fila_da_bancada() -> dict:
    """Z6-11 (24/08/2026): a lista de placeholders abertos, DIRETO do
    `validar-fala-de-tela.py --fila` — a tela passa a *pedir* a medição de
    que precisa, em vez de esperar que alguém lembre (PAREAMENTO-01, "O
    PLACEHOLDER", item b). Mesma disciplina de `numeros_do_mapa`: importa em
    vez de reimplementar, para nunca discordar do portão que é dono da conta.
    """
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "validar_fala_de_tela_do_painel", RAIZ / "scripts" / "validar-fala-de-tela.py"
        )
        if spec is None or spec.loader is None:
            return {"erro": "não consegui carregar o validar-fala-de-tela.py"}
        mod = importlib.util.module_from_spec(spec)
        # Registrar ANTES de `exec_module` não é enfeite: o `@dataclass` do
        # módulo (com `from __future__ import annotations`) resolve a
        # anotação em STRING procurando o módulo pelo nome em `sys.modules`
        # — sem isto ele estoura `AttributeError: 'NoneType' object has no
        # attribute '__dict__'`. Medido aqui em 24/08/2026, mesma causa já
        # documentada em `test_check_paridade_transporte.py`.
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        falas = mod.descobre_falas(RAIZ / mod.APP_RELATIVO, RAIZ)
        fila = mod.monta_fila(falas)
        return {
            "itens": [
                {
                    "chave": f.chave,
                    "lado": f.lado,
                    "aba": f.aba,
                    "origem": f.origem,
                    "aberta_em": (f.pendente or {}).get("aberta_em"),
                    "prazo_dias": (f.pendente or {}).get("prazo_dias"),
                    "quem_fecha": (f.pendente or {}).get("quem_fecha"),
                    "o_que_falta": (f.pendente or {}).get("o_que_falta"),
                }
                for f in fila
            ]
        }
    except Exception as exc:  # o painel nunca pode morrer por causa de uma fonte
        return {"erro": f"{type(exc).__name__}: {exc}"}


def _bloco_da_fila(fila: dict) -> str:
    itens = fila.get("itens") or []
    if fila.get("erro"):
        return (
            '<div class="aviso"><p><b>A fila da bancada não pôde ser medida.</b> '
            f'<code>{escape(str(fila["erro"])[:220])}</code></p></div>'
        )
    if not itens:
        return '<p class="quieto">Nenhum placeholder aberto — o registro `Fala` não deve nada à bancada agora.</p>'
    linhas = ""
    for item in sorted(itens, key=lambda i: str(i.get("aberta_em") or "")):
        linhas += (
            "<tr>"
            f'<td>{escape(str(item.get("chave") or ""))}</td>'
            f'<td>{escape(str(item.get("lado") or ""))}</td>'
            f'<td>{escape(str(item.get("aba") or ""))}</td>'
            f'<td class="quieto">{escape(str(item.get("origem") or ""))}</td>'
            f'<td>{escape(str(item.get("aberta_em") or ""))}</td>'
            f'<td>{escape(str(item.get("prazo_dias") or ""))}</td>'
            f'<td>{escape(str(item.get("quem_fecha") or ""))}</td>'
            f'<td>{escape(str(item.get("o_que_falta") or ""))}</td>'
            "</tr>\n"
        )
    return (
        f'<p>{len(itens)} placeholder(s) aberto(s) — a lista de compras da bancada:</p>'
        '<table class="fila"><thead><tr><th>Chave</th><th>Lado</th><th>Aba</th>'
        "<th>Onde</th><th>Aberta em</th><th>Prazo (dias)</th><th>Quem fecha</th>"
        f"<th>O que falta</th></tr></thead><tbody>{linhas}</tbody></table>"
    )


def estado_do_git() -> dict:
    def git(*a: str) -> str:
        try:
            return subprocess.run(
                ["git", *a], cwd=RAIZ, capture_output=True, text=True, timeout=20
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    sujos = [ln for ln in git("status", "--porcelain").splitlines() if ln.strip()]
    return {
        "branch": git("rev-parse", "--abbrev-ref", "HEAD") or "?",
        "head": git("rev-parse", "--short", "HEAD") or "?",
        "assunto": git("log", "-1", "--format=%s"),
        "sujos": len(sujos),
    }


# --- o CARO -----------------------------------------------------------------


def roda_os_caros() -> dict:
    """Roda a suíte e os portões, e devolve o que medir custou minutos."""
    achados: dict = {"medido_em": time.time(), "portoes": {}}

    print("· suíte inteira (pode levar ~8 min)…", flush=True)
    try:
        # SEM `--timeout`: o `pytest-timeout` NÃO está instalado neste projeto,
        # e o pytest recusa a flag com "unrecognized arguments" — exit 4, saída
        # sem nenhum "N passed". O painel engolia isso e reportava `None`
        # verdes, que é pior do que não medir: parece medição.
        #
        # Medido em 23/08/2026, e o defeito era do painel, não da suíte: a
        # mesma suíte rodada à mão devolvia 11.684 verdes.
        p = subprocess.run(
            [".venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=RAIZ, capture_output=True, text=True, timeout=3600,
        )
        cauda = (p.stdout or "")[-4000:]
        m = re.search(r"(\d+) passed", cauda)
        f = re.search(r"(\d+) failed", cauda)
        achados["suite"] = {
            "passed": int(m.group(1)) if m else None,
            "failed": int(f.group(1)) if f else 0,
            "ok": p.returncode == 0,
            # Se o comando nem rodou, isto é o que separa "sem falhas" de
            # "não consegui medir" — e a página tem de dizer a diferença.
            "nao_mediu": m is None,
            "porque": (cauda[-300:].strip() if m is None else ""),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        achados["suite"] = {"erro": str(exc)}

    for nome, cmd in PORTOES:
        print(f"· portão {nome}…", flush=True)
        try:
            p = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=900)
            achados["portoes"][nome] = {
                "ok": p.returncode == 0,
                "cauda": ((p.stdout or "") + (p.stderr or ""))[-320:].strip(),
            }
        except (OSError, subprocess.SubprocessError) as exc:
            achados["portoes"][nome] = {"ok": None, "cauda": f"não rodou: {exc}"}
    return achados


def le_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# --- a PÁGINA ---------------------------------------------------------------

ESTILO = """
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--color-paper); color: var(--color-ink);
  font-family: var(--font-corpo); font-size: var(--text-base); line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
.envelope {
  max-width: 1120px; margin: 0 auto;
  padding: var(--space-lg) var(--space-sm) var(--space-2xl);
}
h1 {
  font-size: var(--text-display); font-weight: 800; letter-spacing: -.02em;
  margin: 0; line-height: 1.05;
}
h1 b { color: var(--color-accent); font-weight: 800; }
h2 {
  font-size: var(--text-xs); font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
  color: var(--color-ink-faint); margin: var(--space-xl) 0 0;
  padding-bottom: var(--space-2xs); border-bottom: var(--rule-hair) solid var(--color-rule);
}
.lede {
  color: var(--color-ink-quiet); max-width: 66ch;
  margin: var(--space-sm) 0 0; font-size: var(--text-lg);
}
.selo { font-family: var(--font-dado); font-size: var(--text-xs); color: var(--color-ink-faint);
        letter-spacing: .1em; text-transform: uppercase; margin: 0 0 var(--space-xs); }

.grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
         gap: var(--rule-hair); background: var(--color-rule);
         border: var(--rule-hair) solid var(--color-rule); border-radius: var(--radius-md);
         overflow: hidden; margin-top: var(--space-md); }
.kpi {
  background: var(--color-paper-2);
  padding: var(--space-xs) var(--space-sm) var(--space-2xs);
}
.kpi .n {
  font-size: var(--text-2xl); font-weight: 800; line-height: 1;
  font-variant-numeric: tabular-nums; letter-spacing: -.02em;
  font-family: var(--font-dado);
}
.kpi .l {
  font-size: var(--text-xs); color: var(--color-ink-quiet);
  margin-top: var(--space-3xs); line-height: 1.4;
}
.ok { color: var(--color-ok); } .lac { color: var(--color-lacuna); }
.mal { color: var(--color-alerta); } .ac { color: var(--color-accent); }
.frio { color: var(--color-frio); } .quieto { color: var(--color-ink-faint); }

.rolo { overflow-x: auto; margin-top: var(--space-sm);
        border: var(--rule-hair) solid var(--color-rule); border-radius: var(--radius-md); }
table {
  border-collapse: collapse; width: 100%; min-width: 520px;
  background: var(--color-paper-2);
}
th, td { text-align: left; padding: var(--space-2xs) var(--space-sm);
         border-bottom: var(--rule-hair) solid var(--color-rule); font-size: var(--text-sm);
         vertical-align: top; }
th { font-family: var(--font-dado); font-size: var(--text-xs); letter-spacing: .08em;
     text-transform: uppercase; color: var(--color-ink-faint); font-weight: 400;
     background: var(--color-paper-3); }
tr:last-child td { border-bottom: none; }
td.dado { font-family: var(--font-dado); font-variant-numeric: tabular-nums; white-space: nowrap; }

.pendente {
  background: var(--color-paper-2); border: var(--rule-hair) solid var(--color-rule);
  border-left: 3px solid var(--color-accent); border-radius: var(--radius-md);
  padding: var(--space-xs) var(--space-sm); margin-top: var(--space-2xs);
}
.pendente.feita { border-left-color: var(--color-ok); opacity: .72; }
.pendente > summary {
  cursor: pointer; list-style: none; display: flex; gap: var(--space-2xs);
  align-items: baseline; flex-wrap: wrap; font-weight: 600;
}
.pendente > summary::-webkit-details-marker { display: none; }
.pendente > summary::before { content: "▸"; color: var(--color-accent); font-weight: 400; }
.pendente[open] > summary::before { content: "▾"; }
.pendente .id {
  font-family: var(--font-dado); font-size: var(--text-xs); color: var(--color-ink-faint);
  letter-spacing: .06em; margin-left: auto;
}
.pendente dl { margin: var(--space-xs) 0 0; display: grid; grid-template-columns: max-content 1fr;
  gap: var(--space-3xs) var(--space-sm); font-size: var(--text-sm); }
.pendente dt {
  font-family: var(--font-dado); font-size: var(--text-xs); letter-spacing: .08em;
  text-transform: uppercase; color: var(--color-ink-faint); padding-top: .18em;
}
.pendente dd { margin: 0; color: var(--color-ink-quiet); max-width: 74ch; }
.pendente dd.rec { color: var(--color-ok); }
.pendente dd.custo { color: var(--color-lacuna); }
.pendente .olho {
  margin-top: var(--space-xs); display: flex;
  gap: var(--space-sm); flex-wrap: wrap;
}
.pendente .olho figure { margin: 0; max-width: 340px; }
.pendente .olho img {
  max-width: 100%; height: auto; border: var(--rule-hair) solid var(--color-rule);
  border-radius: var(--radius-sm); display: block;
}
.pendente .olho figcaption {
  font-family: var(--font-dado); font-size: var(--text-xs);
  color: var(--color-ink-faint); margin-top: var(--space-3xs);
}
.aviso { margin-top: var(--space-sm); padding: var(--space-xs) var(--space-sm);
         border-radius: var(--radius-md); background: var(--color-paper-2);
         border: var(--rule-hair) solid var(--color-lacuna); font-size: var(--text-sm); }
.aviso b { color: var(--color-lacuna); }
.aviso p { margin: 0; max-width: 70ch; } .aviso p + p { margin-top: var(--space-2xs); }
code { font-family: var(--font-dado); font-size: .92em; color: var(--color-frio); }
footer { margin-top: var(--space-xl); padding-top: var(--space-sm);
         border-top: var(--rule-hair) solid var(--color-rule);
         font-size: var(--text-sm); color: var(--color-ink-faint); max-width: 74ch; }
footer a { color: var(--color-accent); }
"""


def _kpi(n: str, rotulo: str, cor: str = "ac") -> str:
    return (
        f'<div class="kpi"><div class="n {cor}">{n}</div>'
        f'<div class="l">{escape(rotulo)}</div></div>'
    )


def _bloco_das_decisoes(decisoes: list[dict]) -> str:
    """A seção que encabeça o painel: o que espera a palavra dela.

    Cada decisão abre num `<details>` com a pergunta, a recomendação, **o preço
    de decidir para o outro lado**, e — quando existe — a FOTO. Mostrar o preço
    ao lado da recomendação é o que separa esta seção de uma lista de pendências:
    ela decide vendo, e ver inclui ver o custo.

    As já decididas continuam na página, esmaecidas e com a data. Decisão medida
    não se apaga nesta casa.
    """
    if not decisoes:
        return ""

    abertas = [d for d in decisoes if (d.get("estado") or "").strip() != "decidida"]
    feitas = [d for d in decisoes if (d.get("estado") or "").strip() == "decidida"]

    def _fotos(d: dict) -> str:
        pecas = []
        for campo, legenda in (("foto_antes", "como está hoje"), ("foto_depois", "como ficaria")):
            caminho = (d.get(campo) or "").strip()
            if caminho and (RAIZ / caminho).exists():
                pecas.append(
                    f'<figure><img src="{escape(caminho)}" alt="{escape(legenda)}" loading="lazy">'
                    f"<figcaption>{escape(legenda)}</figcaption></figure>"
                )
        return f'<div class="olho">{"".join(pecas)}</div>' if pecas else ""

    def _uma(d: dict, feita: bool) -> str:
        linhas = [("a pergunta", d.get("a_pergunta", ""), "")]
        if d.get("caminhos"):
            linhas.append(("os caminhos", d["caminhos"].replace(" | ", " · "), ""))
        if d.get("recomendacao"):
            linhas.append(("recomendo", d["recomendacao"], "rec"))
        if d.get("preco_do_outro_lado"):
            linhas.append(("o preço do outro lado", d["preco_do_outro_lado"], "custo"))
        if d.get("por_que_espera"):
            linhas.append(("por que espera você", d["por_que_espera"], ""))
        if d.get("custo"):
            linhas.append(("custo", d["custo"], ""))
        if d.get("onde_mora"):
            linhas.append(("onde mora", d["onde_mora"], ""))
        if feita and d.get("escolha"):
            linhas.append(("você escolheu", f'{d["escolha"]} ({d.get("decidida_em", "")})', "rec"))

        # A classe sai FORA da f-string: aspas escapadas dentro de f-string só
        # existem no Python 3.12, e o `pyproject.toml` desta casa declara
        # `requires-python = ">=3.10"`. Rodava nesta bancada e quebraria na
        # máquina de quem tem 3.10 ou 3.11 — que é o vício de bancada que esta
        # leva existe para caçar. O `ruff` acusou.
        pedacos = []
        for rot, txt, cls in linhas:
            if not txt:
                continue
            atributo = f' class="{cls}"' if cls else ""
            pedacos.append(
                f"<dt>{escape(rot)}</dt><dd{atributo}>{escape(txt)}</dd>"
            )
        dl = "".join(pedacos)
        return (
            f'<details class="pendente{" feita" if feita else ""}">'
            f'<summary>{escape(d.get("titulo", d.get("id", "?")))}'
            f'<span class="id">{escape(d.get("id", ""))}</span></summary>'
            f"<dl>{dl}</dl>{_fotos(d)}</details>"
        )

    corpo = "".join(_uma(d, False) for d in abertas)
    corpo += "".join(_uma(d, True) for d in feitas)
    quantas = len(abertas)
    return f"""
  <h2>O que espera você <span class="co">{quantas} decisão(ões) aberta(s)</span></h2>
  <p class="lede" style="font-size:var(--text-sm);margin-top:var(--space-2xs)">
     Nenhuma destas é conserto de código — são escolhas de produto, e a palavra é
     sua. Cada uma abre com <strong>o preço de decidir para o outro lado</strong>,
     porque decidir vendo inclui ver o custo. A fonte é
     <code>docs/data/decisoes-dela.csv</code>: responda lá, ou me diga, e o painel
     acompanha. <strong>Decisão respondida não some</strong> — fica no fim, com a data.</p>
{corpo}
"""


def _idade(medido_em: float | None) -> tuple[str, bool]:
    """Devolve a frase da idade e se o número ainda vale como 'de agora'."""
    if not medido_em:
        return ("nunca medido", False)
    h = (time.time() - float(medido_em)) / 3600.0
    quando = datetime.fromtimestamp(float(medido_em)).strftime("%d/%m às %H:%M")
    if h < 1:
        return (f"medido {quando}", True)
    if h < TETO_DE_FRESCOR_H:
        return (f"medido {quando} · há {h:.0f} h", True)
    return (f"medido {quando} · há {h/24:.0f} dia(s) — VELHO", False)


def monta(rapido: dict, cache: dict) -> str:
    censo, mapa, git = rapido["censo"], rapido["mapa"], rapido["git"]
    bloco_decisoes = _bloco_das_decisoes(rapido.get("decisoes") or [])
    bloco_fila = _bloco_da_fila(rapido.get("fila") or {})
    suite = cache.get("suite") or {}
    portoes = cache.get("portoes") or {}
    frase_idade, fresco = _idade(cache.get("medido_em"))

    vermelhos = [n for n, v in portoes.items() if v.get("ok") is False]
    naorodou = [n for n, v in portoes.items() if v.get("ok") is None]

    kpis = [
        _kpi(str(censo["arquivos"]), "arquivos de sprint na árvore", "ac"),
        _kpi(str(censo["fora_da_fila"]), "não citados no SPRINT_ORDER", "lac"),
        _kpi(str(mapa.get("chaves", "?")), "chaves no mapa de canais", "frio"),
        _kpi(str(mapa.get("assimetrias", "?")), "features que divergem cabo × rádio", "lac"),  # noqa: RUF001
        _kpi(str(mapa.get("sem_teste", "?")), "linhas sem teste que morda", "mal"),
    ]
    abertas = len([
        d for d in (rapido.get("decisoes") or [])
        if (d.get("estado") or "").strip() != "decidida"
    ])
    if abertas:
        kpis.insert(0, _kpi(str(abertas), "decisões esperando você", "ac"))
    if suite.get("passed") is not None:
        cor = "ok" if suite.get("ok") else "mal"
        kpis.append(_kpi(f'{suite["passed"]:,}'.replace(",", "."), "testes verdes", cor))
    elif suite.get("nao_mediu"):
        # Ausência de medição se DECLARA. A versão anterior deixava o KPI de
        # fora e a página ficava igual à de quem nunca rodou a suíte — que é
        # exatamente a mentira por omissão que este painel existe para não
        # contar.
        kpis.append(_kpi("—", "a suíte NÃO foi medida", "lac"))
    if portoes:
        cor = "ok" if not vermelhos else "mal"
        kpis.append(_kpi(f"{len(portoes) - len(vermelhos) - len(naorodou)}/{len(portoes)}",
                         "portões verdes", cor))

    linhas_portao = ""
    for nome, _cmd in PORTOES:
        v = portoes.get(nome)
        if v is None:
            marca, cor, cauda = "não medido", "quieto", "rode com <code>--completo</code>"
        elif v.get("ok") is True:
            marca, cor, cauda = "verde", "ok", escape(v.get("cauda", "")[:110])
        elif v.get("ok") is False:
            marca, cor, cauda = "VERMELHO", "mal", escape(v.get("cauda", "")[:220])
        else:
            marca, cor, cauda = "não rodou", "lac", escape(v.get("cauda", "")[:160])
        linhas_portao += (
            f'<tr><td>{escape(nome)}</td>'
            f'<td class="dado {cor}">{marca}</td>'
            f'<td class="quieto">{cauda}</td></tr>\n'
        )

    alerta = ""
    if suite.get("nao_mediu"):
        alerta += (
            '<div class="aviso"><p><b>A suíte não pôde ser medida.</b> O comando '
            'terminou sem dizer quantos testes passaram, então não há número — e '
            '<em>nenhum número</em> não é o mesmo que <em>nenhuma falha</em>.</p>'
            f'<p class="quieto">O que ele disse no fim: <code>'
            f'{escape((suite.get("porque") or "(nada)")[-220:])}</code></p></div>'
        )
    if not fresco and cache:
        alerta = (
            '<div class="aviso"><p><b>Os números caros estão velhos.</b> '
            f'{escape(frase_idade)}. A árvore andou desde então; o que está abaixo '
            'descreve o passado. Rode <code>python3 scripts/gerar-painel.py '
            '--completo</code>.</p></div>'
        )
    elif not cache:
        alerta = (
            '<div class="aviso"><p><b>A suíte e os portões nunca foram medidos '
            'por este painel.</b> '
            'Os números rápidos acima são de agora; os caros não existem ainda. '
            'Rode <code>python3 scripts/gerar-painel.py --completo</code>.</p>'
            '<p>Vazio aqui é <em>não medimos</em>, nunca <em>está tudo bem</em> — '
            'é a mesma regra do mapa de canais.</p></div>'
        )

    agora = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y às %H:%M")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hefesto · painel do projeto</title>
<style>
/* ARQUIVO GERADO por scripts/gerar-painel.py — não edite à mão.
 * Paleta e tipografia: scripts/paleta_da_casa.py, dividida com o specs.html.
 * Autocontido: zero rede, zero CDN, zero fonte web. */
{TOKENS}{ESTILO}
</style>
</head>
<body>
<div class="envelope">

  <p class="selo">gerado em {agora} · branch {escape(git['branch'])} · {escape(git['head'])}</p>
  <h1><b>Hefesto</b> · painel do projeto</h1>
  <p class="lede">O irmão do <a href="specs.html">mapa de canais</a>. Aquele responde
     <em>o que o aparelho entende</em>; este responde <em>onde o projeto está</em>.
     Os números do mapa aqui não são recontados — vêm do mesmo gerador, para os dois
     não terem como discordar.</p>

  <div class="grade">{''.join(kpis)}</div>
  {alerta}
{bloco_decisoes}

  <h2>Os portões</h2>
  <div class="rolo"><table>
    <thead><tr><th>portão</th><th>estado</th><th>o que ele disse</th></tr></thead>
    <tbody>
{linhas_portao}    </tbody>
  </table></div>
  <p class="lede" style="font-size:var(--text-sm)">{escape(frase_idade)}.
     Portão verde não prova que ele mede o que promete — a casa já achou três
     instrumentos falsos num dia só. Verde aqui quer dizer <em>não acusou</em>.</p>

  <h2>A fila da bancada</h2>
  <p class="lede">Cada <code>Fala</code> declarada com <code>pendente=</code>
     — a tela ainda não sabe o que dizer porque a medição não chegou. Gerado
     direto de <code>scripts/validar-fala-de-tela.py --fila</code>; a lista de
     compras que a interface pede sozinha, sem precisar que alguém lembre.</p>
  <div class="rolo">{bloco_fila}</div>

  <h2>As sprints</h2>
  <div class="grade">
    {_kpi(str(censo['arquivos']), 'arquivos', 'ac')}
    {_kpi(str(censo['diz_aberta']), 'carregam a palavra ABERTA', 'lac')}
    {_kpi(str(censo['diz_concluida']), 'carregam CONCLUÍDA ou FECHADA', 'ok')}
    {_kpi(str(censo['indices']), 'índices', 'quieto')}
    {_kpi(str(censo['citadas_na_fila']), 'citadas no SPRINT_ORDER', 'frio')}
    {_kpi(str(censo['fora_da_fila']), 'fora da fila', 'mal')}
  </div>
  <div class="aviso"><p><b>Esta contagem NÃO classifica.</b> Ela conta arquivos e
     conta quantos carregam a palavra — e as duas somas se sobrepõem de propósito:
     o <code>SPRINT_ORDER.md</code> registra seis sprints com cabeçalho de concluída
     ACIMA de um <code>Status: ABERTA</code> preservado de propósito.</p>
     <p>Um classificador que fingisse resolver isso produziria número convincente e
     falso, que é a armadilha mais cara desta casa. O julgamento de estado é do
     batedor de sprints; aqui fica só o que dá para contar sem julgar.</p></div>

  <h2>O mapa de canais</h2>
  <div class="grade">
    {_kpi(str(mapa.get('chaves', '?')), 'chaves', 'ac')}
    {_kpi(str(mapa.get('linhas', '?')), 'linhas (chave x controle)', 'frio')}
    {_kpi(str(mapa.get('assimetrias', '?')), 'divergem entre cabo e rádio', 'lac')}
    {_kpi(str(mapa.get('sem_teste', '?')), 'sem teste que morda', 'mal')}
  </div>
  <p class="lede" style="font-size:var(--text-sm)">Enquanto a última coluna não
     zerar, o mapa mede o que a casa <em>acredita</em>, não o que ela
     <em>garante</em>: se aquela feature quebrar naquele transporte, a suíte
     inteira continua verde. Os detalhes estão no <a href="specs.html">specs.html</a>.</p>

  <footer>
    <p>Gerado por <code>scripts/gerar-painel.py</code>. Autocontido de propósito —
       um arquivo, sem rede, sem servidor, sem venv: um instrumento que só funciona
       com internet não serve para depurar rádio.</p>
    <p>Os números rápidos (sprints, mapa, git) são de agora, sempre. Os caros
       (suíte, portões) vêm de <code>docs/data/painel-cache.json</code> e carregam a
       idade ao lado. <strong>Ausência de medição é declarada, nunca preenchida com
       zero</strong> — é a mesma regra do mapa de canais, e existe porque zero pinta
       verde.</p>
    <p>Árvore: {git['sujos']} arquivo(s) com mudança não commitada em
       <code>{escape(git['head'])}</code> — <em>{escape(git['assunto'][:96])}</em>.</p>
  </footer>

</div>
</body>
</html>
"""


def _recorta_selo(pagina: str) -> list[str]:
    """Tira as linhas que mudam a cada geração, para o --check comparar conteúdo."""
    fora = ("gerado em", "Árvore:", "medido ", "nunca medido")
    return [ln for ln in pagina.splitlines() if not any(m in ln for m in fora)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--completo", action="store_true",
                    help="roda a suíte e os portões, e regrava o cache")
    ap.add_argument("--check", action="store_true",
                    help="o painel.html publicado bate com as fontes de agora?")
    args = ap.parse_args()

    if args.completo:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(roda_os_caros(), indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
        print(f"cache regravado em {CACHE.relative_to(RAIZ)}")

    rapido = {
        "censo": censo_de_sprints(),
        "mapa": numeros_do_mapa(),
        "git": estado_do_git(),
        "decisoes": decisoes_dela(),
        "fila": fila_da_bancada(),
    }
    pagina = monta(rapido, le_cache())

    if args.check:
        publicado = _texto(SAIDA)
        if not publicado:
            print("painel.html: NÃO EXISTE — rode `python3 scripts/gerar-painel.py`")
            return 1
        if _recorta_selo(publicado) != _recorta_selo(pagina):
            print("painel.html: DESATUALIZADO — o conteúdo não bate com as fontes.")
            print("  cure com: python3 scripts/gerar-painel.py")
            return 1
        print("painel.html: atualizado (confere com as sprints, o CSV e o cache)")
        return 0

    SAIDA.write_text(pagina, encoding="utf-8")
    censo = rapido["censo"]
    print(f"painel.html: {censo['arquivos']} sprints, "
          f"{rapido['mapa'].get('chaves', '?')} chaves do mapa, "
          f"{_idade(le_cache().get('medido_em'))[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
