#!/usr/bin/env python3
"""bancada_do_mapa.py — a superfície de MEDIÇÃO do mapa de canais."""
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
        "    .venv/bin/pip install -e \".[bancada]\"\n"
        "    .venv/bin/streamlit run scripts/bancada_do_mapa.py"
    ) from e

AQUI = Path(__file__).resolve().parent
RAIZ = Path(__file__).resolve().parents[1]
CSV_ = RAIZ / "docs" / "data" / "mapa-controles.csv"
ENSAIOS_ = RAIZ / "docs" / "data" / "ensaios.csv"

sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ / "src"))
import eliminacao

EDITAVEIS = ["cabo_ate_onde_foi", "radio_ate_onde_foi", "provado_em", "provado_por",
             "validade_dias", "estado_hoje", "teste_que_morde", "mordida",
             "mordida_provada_em", "assimetria_declarada",
             "cabo_ressalva", "radio_ressalva"]

from check_paridade_transporte import VALORES_DA_ESCADA

GRAUS = ["", *VALORES_DA_ESCADA]

from hefesto_dualsense4unix.integrations.ponte_escada import ESCADA

PONTES = ["", *[degrau.ponte.chave for degrau in ESCADA]]
QUEM = ["", "ci", "bancada", "olho-dela",
        "aparelho", "fonte-do-driver", "descritor", "instrumento"]
_ESTADO_RUMBLE_SIMULTANEO = (
    "RESPONDIDA em 11/08/2026 com a mesa cheia, e a causa do estorvo esta ISOLADA: quatro"
    " controles vibram ao mesmo tempo nos dois transportes; o que os cancelava era o "
    "keepalive do daemon, provado por dose-resposta. Fica ABERTA a cura — o keepalive não"
    " pode escrever zero nos bytes de motor sem saber se ha um dono de fora — e fica "
    "aberto por que o cancelamento e total com dois alvos e apenas parcial com quatro."
)
_ESTADO_RUMBLE_FF = (
    "MEDIDO nos dois transportes em 11/08/2026 com quatro controles na mesa, e a causa esta "
    "FECHADA: o keepalive do daemon cancela o rumble alheio, e o faz pelos BYTES de motor, "
    "não pelos bits — provado por dose-resposta (0,5s -> pulso; 8,0s -> oito segundos) e "
    "por troca de lado (bits desligados trocaram o motor que vibra). A cura ESTA escrita e "
    "LIGADA: `OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC = 2.0` "
    "(core/backend_pydualsense.py:212), consumida no laco vivo em :926-932, com mordida em "
    "tests/unit/test_rumble_sem_dono_01.py. O que ela NAO tem e medicao de radio: a mordida "
    "prova o LACO, nunca o motor."
)
_ESTADO_GIROSCOPIO_BIAS = (
    'Fechado nos dois transportes em 15/08/2026 pelo E-8. O número de repouso NÃO é zero: '
    'as quatro unidades ficam entre 0,19 e 1,53 graus/s de bias de velocidade angular, '
    'porque o driver zera o `bias` do giroscópio de propósito (`hid-playstation.c:1200, '
    ':1206, :1212`) e só normaliza a escala. É bias de fábrica por unidade, não ruído e '
    'não transporte — um jogo que integrar sem corrigir deriva de 0,2 a 1,5 grau por '
    'segundo.'
)
_ESTADO_IMU_LIGAR = (
    'PERGUNTA FECHADA POR BUSCA, 15/08/2026: NÃO existe, nesta árvore, código que tente '
    'ligar a IMU do DualSense — logo não há nada a podar aqui. O `set_motion_streaming` é '
    'flag DO VPAD (decide se o espelho emite) e o único Enable-IMU do projeto é o '
    'subcomando 0x40 do protocolo Switch, em `core/external_leds.py:142`, que é do '
    'Nintendo Pro REAL. Procurado por `git grep` em `imu`, `motion`, `enable_motion` e '
    '`ligar` sobre `src/` e `app/`.'
)
_ESTADO_IMU_PERDA = (
    'A assimetria "uma degradação de link no CABO é invisível para a telemetria" tem cura '
    'medida e NÃO aplicada: o `__le32` de `corpo[11..14]` é contador de reports nos DOIS '
    'transportes, e o produto hoje não o lê em transporte nenhum. Parseá-lo daria ao cabo '
    'o contador que ele nunca teve e ao rádio um que mede perda de verdade, em vez do '
    '`bt_drops`, que conta o que o PRODUTO descartou.'
)
_ESTADO_BRILHO_DO_PERFIL = (
    'o perfil escolhe o brilho das luzes de número por controle — Fraco, '
    'Médio ou Forte (`leds.player_led_brightness`, no global e no override de '
    'cada controle), e todo controle nasce no Fraco (o degrau 2). O produto '
    'manda o `flag2` bit0 com o degrau nos dois transportes: no cabo sem nó '
    'gravável, pelo fluxo; no cabo com o nó do kernel, num 0x02 avulso logo '
    'depois do número; no rádio, no 0x31 que acende o número. Vale para o '
    '«Todos» do perfil, para um controle só, para o clique da linha LEDs '
    '(`led.player_brightness_set`) e para o controle que chega depois, e a '
    'escolha sobrevive à troca de perfil, ao «Salvar Perfil» do rodapé e ao '
    'Estilo de Jogo. A pílula da aba Iluminação acende o degrau que o daemon '
    'diz aceso naquele controle (`daemon.state_full` → '
    '`controllers[].brilho_das_luzes`, o merge com a camada da usuária), e '
    'por isso o clique sobrevive à troca automática também na tela; sem o '
    'daemon, ou com um daemon que não publica a chave, ela cai no perfil do '
    'disco. Ver O-BRILHO-DAS-LUZES-DE-NUMERO-01 e '
    'A-04-PERGUNTA-AO-DAEMON-VIVO-01.'
)
ESTADOS = ["", "funciona", "regrediu", "nunca funcionou",
           "não implementado", "impossível",
           _ESTADO_RUMBLE_SIMULTANEO, _ESTADO_RUMBLE_FF,
           _ESTADO_GIROSCOPIO_BIAS, _ESTADO_IMU_LIGAR, _ESTADO_IMU_PERDA,
           _ESTADO_BRILHO_DO_PERFIL]
LADOS = {"cabo": "cabo_", "rádio": "radio_"}

st.set_page_config(page_title="Hefesto · bancada de medição", layout="wide")


@st.cache_data
def carrega(mtime: float) -> pd.DataFrame:
    return pd.read_csv(CSV_, dtype=str, keep_default_na=False)


df = carrega(CSV_.stat().st_mtime)

st.title("Bancada de medição")
st.caption(
    f"{len(df)} linhas · a régua é o degrau de cada lado "
    "(`cabo_ate_onde_foi` / `radio_ate_onde_foi`): "
    "**MONTOU** (o produto montou o report) "
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
        "cabo_ate_onde_foi":
            st.column_config.SelectboxColumn("cabo_ate_onde_foi", options=GRAUS),
        "radio_ate_onde_foi":
            st.column_config.SelectboxColumn("radio_ate_onde_foi", options=GRAUS),
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

    CORES = {"culpado": "\u25cf", "inconclusivo": "\u25d0", "confuso": "\u25d1",
             "inocente": "\u25cb", "nunca-investigado": "\u25cc"}
    _SEM_COR = "\u25cc"
    st.markdown(f"### {CORES.get(estado, _SEM_COR)} {estado.upper()}")
    st.caption(agora)

    for j in eliminacao.julga_linha(ens):
        with st.container(border=True):
            st.markdown(f"**{CORES.get(j.veredicto, _SEM_COR)} {j.suspeito}**")
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
        susp_ant = c1.selectbox("Suspeito já levantado", ["— novo suspeito —", *sugeridos])
        presente = c2.radio("O suspeito estava", ["COM", "SEM"], horizontal=True)
        susp_novo = st.text_input(
            "Suspeito novo",
            placeholder="o que você está testando (ex.: 0x08 na janela de 3,4 s)",
        )
        c3, c4 = st.columns(2)
        resultado = c3.text_input("Resultado", placeholder="obedece / não obedece / acendeu / mudo")
        quem = c4.selectbox("Observado por", ["olho-dela", "bancada", "ci"])
        degrau_medido = st.selectbox(
            "Até onde este ensaio mediu?",
            GRAUS,
            help="Deixe vazio se o ensaio mediu a IDA (produto -> aparelho), que "
                 "é o caso de todos os 177 do caderno. Preencha quando tiver "
                 "medido a VOLTA (aparelho -> vpad -> JOGO): sem esta palavra o "
                 "ensaio não sustenta `O JOGO RECEBEU` nem `O JOGO REAGIU`.",
        )
        # ela chegou — máscara DualSense, máscara Xbox, nativo, ou Steam Input.
        ponte_medida = st.selectbox(
            "Por qual ponte este ensaio mediu?",
            PONTES,
            help="Deixe vazio se o ensaio falou direto com o aparelho (hidraw, "
                 "sem jogo e sem vpad no meio), que é o caso dos 177 do "
                 "caderno. Preencha quando houver um JOGO do outro lado: a "
                 "ponte é a máscara/modo por onde ele recebeu.",
        )
        feature = st.selectbox(
            "E a FEATURE, obedeceu? (só se for diferente do Resultado)",
            ["", "obedece", "não obedece", "parcial", "inconclusivo"],
            help="Preencha quando o `Resultado` acima estiver falando do "
                 "SUSPEITO e não do que o aparelho fez. Divergir dos dois "
                 "EXIGE nota — é o que o portão cobra (regra 12).",
        )
        nota = st.text_input("Nota", placeholder="o que mais estava valendo neste ensaio")

        if st.form_submit_button("Gravar ensaio", type="primary"):
            susp = susp_novo.strip() or (susp_ant if susp_ant != "— novo suspeito —" else "")
            if not susp or not resultado.strip():
                st.error("suspeito e resultado são obrigatórios — "
                         "ensaio sem os dois não julga nada")
            else:
                novo = {
                    "id": f"{linha_id.split('.')[0]}-{lado}-"
                          f"{len(cadernos.get((linha_id, lado), [])) + 1}-"
                          f"{datetime.now():%H%M%S}",
                    "linha_id": linha_id,
                    "transporte": lado,
                    "degrau": degrau_medido,
                    "ponte": ponte_medida,
                    "quando": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "suspeito": susp,
                    "presente": "sim" if presente == "COM" else "não",
                    "resultado": resultado.strip(),
                    "resultado_da_feature": feature,
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
    f"hoje é {date.today():%Y-%m-%d} · uma prova sem data é folclore, e um lado "
    "com `O APARELHO OBEDECEU` só vale com ensaio no caderno cujo "
    "`observado_por` seja `olho-dela` — é o que o portão cobra."
)
