#!/usr/bin/env python3
"""bancada.py — a superfície de MEDIÇÃO do mapa de canais.

O `specs.html` é o artefato: consulta, versiona, abre em qualquer lugar sem
servidor. Esta bancada é o oposto — existe para o momento em que ela está com o
controle na mão, mede uma coisa, e precisa gravar o que mediu no mesmo CSV.

Os dois leem e escrevem `docs/data/mapa-controles.csv`. Depois de gravar aqui,
rode `python3 scripts/gerar-mapa.py` para o artefato acompanhar — o portão
`--check` reprova se você esquecer.

Desde a migração v2 o grão é `(chave, controle)`: uma feature de um controle é
UMA linha, com o cabo e o rádio lado a lado em colunas `cabo_*` / `radio_*`. O
caderno de eliminação, porém, continua julgando os dois lados SEPARADAMENTE —
juntá-los faria os sete ensaios da lightbar por rádio brigarem com o do cabo e
o veredicto viraria "os ensaios se contradizem".

    .venv/bin/pip install streamlit      # não é dependência do produto
    .venv/bin/streamlit run bancada.py
"""
from __future__ import annotations

import csv
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import pandas as pd
    import streamlit as st
except ModuleNotFoundError as e:      # pragma: no cover - caminho de ajuda
    raise SystemExit(
        f"falta {e.name}. A bancada NÃO é dependência do produto — instale só nela:\n"
        "    .venv/bin/pip install streamlit pandas\n"
        "    .venv/bin/streamlit run bancada.py"
    ) from e

RAIZ = Path(__file__).resolve().parent
CSV_ = RAIZ / "docs" / "data" / "mapa-controles.csv"
ENSAIOS_ = RAIZ / "docs" / "data" / "ensaios.csv"

sys.path.insert(0, str(RAIZ / "scripts"))
import eliminacao  # noqa: E402

#: Só estas colunas se escrevem daqui. As outras vieram da escavação e mudam
#: por auditoria, não por digitação — é o que impede a bancada de virar um
#: editor de fatos.
EDITAVEIS = ["grau", "provado_em", "provado_por", "validade_dias",
             "estado_hoje", "teste_que_morde", "mordida", "mordida_provada_em",
             "assimetria_declarada", "ressalva"]

GRAUS = ["", "MONTOU", "SAIU NO FIO", "O APARELHO OBEDECEU"]
QUEM = ["", "ci", "bancada", "olho-dela"]
ESTADOS = ["", "funciona", "regrediu", "nunca funcionou",
           "não implementado", "impossível"]
LADOS = {"cabo": "cabo_", "rádio": "radio_"}

st.set_page_config(page_title="Hefesto · bancada de medição", layout="wide")


@st.cache_data
def carrega(mtime: float) -> pd.DataFrame:
    return pd.read_csv(CSV_, dtype=str, keep_default_na=False)


df = carrega(CSV_.stat().st_mtime)

st.title("Bancada de medição")
st.caption(
    f"{len(df)} linhas · a régua é `grau`: **MONTOU** (o produto montou o report) "
    "→ **SAIU NO FIO** (o byte saiu e algo voltou) → **O APARELHO OBEDECEU** "
    "(acendeu, girou, endureceu, saiu som). Tratar *montou* como *funciona* é a "
    "mentira mais cara desta casa."
)

c1, c2, c3, c4 = st.columns(4)
ctrl = c1.multiselect("Controle", sorted(df.controle.unique()))
tran = c2.multiselect("Transporte no v1", sorted(df.transporte.unique()))
fam = c3.multiselect("Família", sorted(df.familia.unique()))
recorte = c4.selectbox(
    "Recorte",
    ["tudo", "sem teste que morde", "sem prova", "o aparelho tem e o produto não faz",
     "cabo e rádio divergem", "ninguém respondeu"],
)

v = df
if ctrl:
    v = v[v.controle.isin(ctrl)]
if tran:
    v = v[v.transporte.isin(tran)]
if fam:
    v = v[v.familia.isin(fam)]
if recorte == "sem teste que morde":
    v = v[v.teste_que_morde.str.strip() == ""]
elif recorte == "sem prova":
    v = v[v.provado_em.str.strip() == ""]
elif recorte == "o aparelho tem e o produto não faz":
    v = v[(v.existe == "tem") & (v.cabo_aciona != "sim") & (v.radio_aciona != "sim")]
elif recorte == "cabo e rádio divergem":
    v = v[(v.cabo_aceita != "") & (v.radio_aceita != "")
          & ((v.cabo_aceita != v.radio_aceita) | (v.cabo_aciona != v.radio_aciona))]
elif recorte == "ninguém respondeu":
    v = v[v.transporte == "sem linha no v1"]

busca = st.text_input("Buscar", placeholder="feature, comando, report, arquivo…")
if busca:
    alvo = (v.chave + " " + v.rotulo + " " + v.peca + " " + v.evdev + " "
            + v.cabo_comando + " " + v.radio_comando + " "
            + v.cabo_report_id + " " + v.radio_report_id + " "
            + v.cabo_codigo_ref + " " + v.radio_codigo_ref).str.lower()
    v = v[alvo.str.contains(busca.lower(), regex=False)]

st.write(f"**{len(v)}** de {len(df)} linhas")

vis = ["chave", "controle", "rotulo", "existe", "transporte",
       "cabo_aceita", "radio_aceita", "cabo_aciona", "radio_aciona",
       "cabo_canal", "radio_canal", "cabo_report_id", "radio_report_id",
       *EDITAVEIS]
editado = st.data_editor(
    v[vis],
    width="stretch",
    hide_index=True,
    disabled=[c for c in vis if c not in EDITAVEIS],
    column_config={
        "grau": st.column_config.SelectboxColumn("grau", options=GRAUS),
        "provado_por": st.column_config.SelectboxColumn("provado_por", options=QUEM),
        "estado_hoje": st.column_config.SelectboxColumn("estado_hoje", options=ESTADOS),
        "provado_em": st.column_config.TextColumn("provado_em", help="AAAA-MM-DD"),
    },
    key="grade",
)

col_a, col_b = st.columns([1, 3])
if col_a.button("Gravar no CSV", type="primary"):
    base = df.copy()
    for col in EDITAVEIS:
        base.loc[editado.index, col] = editado[col]
    base.to_csv(CSV_, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    carrega.clear()
    col_b.success(
        f"gravado em {CSV_.relative_to(RAIZ)} · agora rode "
        "`python3 scripts/gerar-mapa.py` para o specs.html acompanhar"
    )

# ─────────────────────────────────────────────────────────────────────────
# O CADERNO DE ELIMINAÇÃO
#
# É aqui que ela repete, para qualquer feature, o que fez com a lightbar: cria
# um suspeito, ensaia COM ele e ensaia SEM ele, e o instrumento diz se isolou.
# A regra que o eliminacao.py implementa: enquanto só houver ensaio de um lado,
# o veredicto é INCONCLUSIVO e o que aparece é QUAL ensaio falta.
# ─────────────────────────────────────────────────────────────────────────
st.divider()
st.header("Caderno de eliminação")

cadernos = eliminacao.carrega_por_lado(ENSAIOS_)
alvos = v if len(v) < len(df) else df
rotulo = {
    f"{r.chave} · {r.controle} · {r.rotulo[:48]}": r.id
    for r in alvos.itertuples()
}
if not rotulo:
    st.info("nenhuma linha no filtro acima")
else:
    ca, cb = st.columns([3, 1])
    escolha = ca.selectbox("Linha em investigação", list(rotulo))
    lado_rot = cb.radio("Transporte do ensaio", list(LADOS), horizontal=True)
    lado = "cabo" if lado_rot == "cabo" else "radio"
    linha_id = rotulo[escolha]
    ens = cadernos.get((linha_id, lado), [])
    estado, agora = eliminacao.estado_da_linha(ens)

    # Símbolos geométricos, não emoji: o projeto proíbe emoji e há portão
    # (validar-glifos.py). São os MESMOS que o specs.html usa, então o
    # vocabulário visual não se parte entre as duas superfícies.
    CORES = {"culpado": "\u25cf", "inconclusivo": "\u25d0", "confuso": "\u25d1",
             "inocente": "\u25cb", "nunca-investigado": "\u25cc"}
    st.markdown(f"### {CORES.get(estado, "\u25cc")} {estado.upper()}")
    st.caption(agora)

    for j in eliminacao.julga_linha(ens):
        with st.container(border=True):
            st.markdown(f"**{CORES.get(j.veredicto, "\u25cc")} {j.suspeito}**")
            st.caption(
                f"{j.ensaios} ensaio(s) · com: {', '.join(j.com) or '—'} "
                f"· sem: {', '.join(j.sem) or '—'}"
            )
            if j.proximo_ensaio:
                st.warning(f"falta {j.proximo_ensaio}")

    if ens:
        st.dataframe(
            pd.DataFrame(ens)[["quando", "suspeito", "presente", "resultado", "nota"]],
            width="stretch", hide_index=True,
        )

    with st.form("ensaio_novo", clear_on_submit=True):
        st.markdown("**Registrar um ensaio**")
        sugeridos = sorted({e["suspeito"] for e in ens})
        c1, c2 = st.columns([3, 1])
        susp_ant = c1.selectbox("Suspeito já levantado", ["— novo suspeito —"] + sugeridos)
        presente = c2.radio("O suspeito estava", ["COM", "SEM"], horizontal=True)
        susp_novo = st.text_input(
            "Suspeito novo",
            placeholder="o que você está testando (ex.: 0x08 na janela de 3,4 s)",
        )
        c3, c4 = st.columns(2)
        resultado = c3.text_input("Resultado", placeholder="obedece / não obedece / acendeu / mudo")
        quem = c4.selectbox("Observado por", ["olho-dela", "bancada", "ci"])
        nota = st.text_input("Nota", placeholder="o que mais estava valendo neste ensaio")

        if st.form_submit_button("Gravar ensaio", type="primary"):
            susp = susp_novo.strip() or (susp_ant if susp_ant != "— novo suspeito —" else "")
            if not susp or not resultado.strip():
                st.error("suspeito e resultado são obrigatórios — ensaio sem os dois não julga nada")
            else:
                novo = {
                    "id": f"{linha_id.split('.')[0]}-{lado}-"
                          f"{len(cadernos.get((linha_id, lado), [])) + 1}-"
                          f"{datetime.now():%H%M%S}",
                    "linha_id": linha_id,
                    "transporte": lado,
                    "quando": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "suspeito": susp,
                    "presente": "sim" if presente == "COM" else "não",
                    "resultado": resultado.strip(),
                    "observado_por": quem,
                    "fonte": "bancada",
                    "nota": nota.strip(),
                    "linha_id_v1": "",
                }
                existe = ENSAIOS_.exists()
                with open(ENSAIOS_, "a", encoding="utf-8", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(novo), lineterminator="\n")
                    if not existe:
                        w.writeheader()
                    w.writerow(novo)
                depois, oque = eliminacao.estado_da_linha(
                    eliminacao.carrega_por_lado(ENSAIOS_).get((linha_id, lado), []))
                st.success(f"gravado · o veredicto agora é **{depois.upper()}** — {oque}")
                st.caption("rode `python3 scripts/gerar-mapa.py` para o specs.html acompanhar")

st.divider()
st.caption(
    f"hoje é {date.today():%Y-%m-%d} · uma prova sem data é folclore, e uma linha "
    "com `grau=O APARELHO OBEDECEU` só vale com `provado_por=olho-dela`."
)
