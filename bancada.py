#!/usr/bin/env python3
"""bancada.py — a superfície de MEDIÇÃO do mapa de canais.

O `specs.html` é o artefato: consulta, versiona, abre em qualquer lugar sem
servidor. Esta bancada é o oposto — existe para o momento em que ela está com o
controle na mão, mede uma coisa, e precisa gravar o que mediu no mesmo CSV.

Os dois leem e escrevem `docs/data/mapa-controles.csv`. Depois de gravar aqui,
rode `python3 scripts/gerar-mapa.py` para o artefato acompanhar — o `--check`
acusa quem esquecer.

Em 11/08/2026, quando esta linha foi conferida, o `--check` ainda precisava ser
chamado À MÃO: nenhum portão do CI, do pre-commit ou da suíte o invocava. Ele
está escrito e provado nos três casos, mas escrito não é ligado — e chamar de
"portão" o que ninguém chama é o defeito mais caro desta casa.

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
# O `src` entra no caminho pela mesma razão que o `scripts`: a bancada precisa
# do vocabulário de PONTES, e o dono dele é `integrations/ponte_escada.py`.
# Com o install editável do produto o import já funcionaria; sem ele (uma
# `streamlit` de fora do `.venv`, que é como esta bancada costuma ser aberta)
# não funcionaria, e o remédio seria redigitar as quatro pontes aqui — que é
# exatamente a segunda cópia do vocabulário que a nota ESCADA-COM-UM-DONO-SO,
# logo abaixo, existe para não deixar acontecer de novo.
sys.path.insert(0, str(RAIZ / "src"))
import eliminacao  # noqa: E402

#: Só estas colunas se escrevem daqui. As outras vieram da escavação e mudam
#: por auditoria, não por digitação — é o que impede a bancada de virar um
#: editor de fatos.
#:
#: O degrau (`ate_onde_foi`) e a ressalva vêm EM PAR desde a migração v2
#: pela mesma razão que `aceita` e `aciona` vêm: uma feature é UMA linha, e o
#: que muda entre os transportes fica lado a lado na mesma linha. Editar só o
#: lado selecionado seria inventar aqui o modo do caderno de eliminação — que
#: separa os dois de propósito, e cuja razão está na docstring lá em cima.
EDITAVEIS = ["cabo_ate_onde_foi", "radio_ate_onde_foi", "provado_em", "provado_por",
             "validade_dias", "estado_hoje", "teste_que_morde", "mordida",
             "mordida_provada_em", "assimetria_declarada",
             "cabo_ressalva", "radio_ressalva"]

# ESCADA-COM-UM-DONO-SO (19/08/2026). Esta lista era a SEGUNDA cópia do
# vocabulário: o portão tinha a dele e a bancada tinha esta, e em 19/08 os dois
# degraus novos da direção de ENTRADA (`O JOGO RECEBEU`, `O JOGO REAGIU`)
# entraram só no portão — o resultado é que ele os ACEITAVA e o formulário não
# os OFERECIA, então ninguém conseguia escrevê-los. Duas listas do mesmo
# vocabulário divergem no dia em que alguém mexe numa; agora há um dono só.
from check_paridade_transporte import VALORES_DA_ESCADA  # noqa: E402

GRAUS = ["", *VALORES_DA_ESCADA]

# ENSAIO-QUE-NAO-DIZ-A-PONTE-01 (20/08/2026), e a mesma disciplina da linha
# acima: as pontes NÃO se redigitam aqui. Elas saem da `ESCADA` de
# `integrations/ponte_escada.py`, que é quem decide qual ponte o produto tenta
# e em que ordem — se um degrau novo entrar lá, ele aparece neste formulário no
# mesmo instante, sem ninguém lembrar de vir aqui.
from hefesto_dualsense4unix.integrations.ponte_escada import ESCADA  # noqa: E402

#: O `""` na frente é o padrão, e ele quer dizer **"não declarou"** — NUNCA
#: "serve para toda ponte". A distinção não é filosofia: os 177 ensaios do
#: caderno nasceram sem o campo, e ler o vazio deles como "vale para qualquer
#: ponte" transformaria medição feita sem jogo nenhum em prova sobre a ponte que
#: alguém quisesse. Quem consome isto é o `eliminacao.sustentam_a_ponte`, e lá a
#: regra está escrita por extenso.
PONTES = ["", *[degrau.ponte.chave for degrau in ESCADA]]
#: O vocabulário de `provado_por` DIVERGE do que o método declara, e a lista
#: abaixo é a soma dos dois — medido em 12/08/2026, com o CSV na mão:
#: o `METODO-DE-ISOLAMENTO.md` prevê `ci`/`bancada`/`olho-dela`, e o mapa usa
#: `aparelho` (19), `fonte-do-driver` (12) e `descritor` (2). `olho-dela` NÃO
#: aparece em nenhuma das 293 linhas. São duas perguntas diferentes que caíram
#: na mesma coluna: o método pergunta QUEM viu, o mapa responde DE ONDE veio a
#: afirmação. Quem sustenta o degrau `O APARELHO OBEDECEU` é o `observado_por`
#: do CADERNO (`docs/data/ensaios.csv`, `olho-dela` em 53 dos 57), e é lá que o
#: portão foi cobrar (regra 10 do `check_paridade_transporte.py`).
#: Somar em vez de escolher é deliberado: um seletor que não contém nenhum dos
#: 33 valores existentes apaga medição na primeira gravação. Qual vocabulário
#: fica é decisão dela.
QUEM = ["", "ci", "bancada", "olho-dela",
        "aparelho", "fonte-do-driver", "descritor"]
#: BANCADA-ESTADOS-01 (13/08/2026): as duas prosas abaixo NÃO são vocabulário —
#: são o texto que o mapa JÁ tem em `estado_hoje`, nas duas únicas das 293 linhas
#: em que a coluna está preenchida: `combinacao.rumble_simultaneo@dualsense` e
#: `vibracao.rumble.ff@dualsense`, a dose-resposta do keepalive medida em
#: 11/08/2026. Estão aqui pela razão já escrita acima para `provado_por`, e que
#: ninguém tinha aplicado a esta lista.
#:
#: Com os graus de confiança separados, porque eles diferem:
#: - MEDIDO (13/08/2026, `csv.DictReader` sobre as 293 linhas): `estado_hoje` tem
#:   2 valores não vazios, e o `ESTADOS` de antes desta linha não continha
#:   NENHUM dos dois. O seletor estava cego a 100% do dado da coluna.
#: - LIDO NO CÓDIGO: `estado_hoje` está em `EDITAVEIS`, e o botão "Gravar no CSV"
#:   (logo abaixo) regrava TODA coluna editável de toda linha visível, com o que
#:   voltou da grade — não há caminho que preserve o valor original.
#: - INFERIDO: que o `SelectboxColumn` COAJA um valor fora de `options` em vez de
#:   deixá-lo passar. Não foi possível medir: `streamlit` não está instalado
#:   nesta máquina (conferido em 13/08/2026), e ele não é dependência do produto.
#:   É a única parte da cadeia que não foi vista rodar.
#:
#: Somar em vez de escolher é o mesmo gesto do `provado_por`: enquanto a inferência
#: não for derrubada, o lado barato do erro é oferecer o valor que já existe.
#: Transcritas byte a byte, com os acentos que faltam no original: o valor tem de
#: casar com o CSV, e "corrigir" o texto aqui traria de volta a perda que este
#: bloco existe para impedir. O
#: `tests/unit/test_bancada_nomeia_coluna_que_o_csv_nao_tem.py` cruza as opções
#: de todo `SelectboxColumn` com os valores que o CSV realmente tem, e reprova
#: nomeando a coluna e o valor que ficaria órfão — inclusive se a transcrição
#: abaixo divergir de uma letra.
#: Se `estado_hoje` fica sendo vocabulário curto ou texto livre é decisão dela;
#: até ela decidir, o dado não some por omissão.
_ESTADO_RUMBLE_SIMULTANEO = (
    "RESPONDIDA em 11/08/2026 com a mesa cheia, e a causa do estorvo esta ISOLADA: quatro"
    " controles vibram ao mesmo tempo nos dois transportes; o que os cancelava era o "
    "keepalive do daemon, provado por dose-resposta. Fica ABERTA a cura — o keepalive não"
    " pode escrever zero nos bytes de motor sem saber se ha um dono de fora — e fica "
    "aberto por que o cancelamento e total com dois alvos e apenas parcial com quatro."
)
_ESTADO_RUMBLE_FF = (
    "MEDIDO nos dois transportes em 11/08/2026 com quatro controles na mesa, e a causa "
    "esta FECHADA: o keepalive do daemon cancela o rumble alheio, e o faz pelos BYTES de "
    "motor, não pelos bits — provado por dose-resposta (0,5s -> pulso; 8,0s -> oito "
    "segundos) e por troca de lado (bits desligados trocaram o motor que vibra). A cura "
    "ainda NAO foi escrita."
)
#: BANCADA-ESTADOS-02 (15/08/2026): mais TRÊS, e a lista cresceu por medição, não
#: por gosto. O `estado_hoje` recebeu neste dia o bias do giroscópio em repouso, a
#: busca que fechou o `imu.ligar` e o contador de reports do `imu.perda` — as três
#: escritas por quem estava medindo, e as três reprovadas pelo portão, como tinha
#: de ser. Transcritas aqui pela mesma razão de 13/08.
#:
#: A tentação, e por que ela foi DESCARTADA: derivar a lista do próprio CSV em
#: tempo de execução acaba com a transcrição para sempre. Foi escrito, e o
#: `test_a_regua_dos_selectbox_ainda_alcanca_a_grade` reprovou na hora — a régua
#: lê `options` ESTATICAMENTE, pelo AST, e uma lista computada ela não consegue
#: conferir contra o CSV. O incômodo da transcrição é o preço de a régua existir;
#: trocá-lo por conveniência desligaria a guarda em silêncio, que é o defeito que
#: ela guarda. Fica como está até ela decidir se `estado_hoje` é vocabulário curto.
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
    'subcomando 0x40 do protocolo Switch, em `core/external_leds.py:149`, que é do '
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
ESTADOS = ["", "funciona", "regrediu", "nunca funcionou",
           "não implementado", "impossível",
           _ESTADO_RUMBLE_SIMULTANEO, _ESTADO_RUMBLE_FF,
           _ESTADO_GIROSCOPIO_BIAS, _ESTADO_IMU_LIGAR, _ESTADO_IMU_PERDA]
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
    #: PY310-FSTRING-01 (13/08/2026): o glifo de fallback sai para uma constante
    #: porque reaproveitar a aspa de fora DENTRO da f-string só é sintaxe válida
    #: a partir do Python 3.12, e o `pyproject.toml` desta casa declara `py310`.
    #: O `ruff` do pre-commit acusou `invalid-syntax` em 3.10 e 3.11 — ou seja, a
    #: bancada não COMPILAVA nas duas versões que o `ci.yml` testa.
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
        # ENSAIO-QUE-NAO-DIZ-O-DEGRAU-01 (20/08/2026). O ensaio passa a dizer o
        # que ele mediu. As opções saem de `GRAUS`, que sai de `VALORES_DA_ESCADA`
        # — nunca redigitadas, mesma disciplina do resto deste arquivo.
        #
        # O padrão é VAZIO e continua sendo: os 177 ensaios do caderno nasceram
        # sem o campo e vazio quer dizer "não declarou", que é a verdade sobre
        # eles. O que vazio NÃO quer dizer é "serve para tudo" — os dois degraus
        # de ENTRADA exigem declaração, porque foi lá que o portão aceitou ensaio
        # de acender lightbar como prova de que um JOGO REAGIU.
        degrau_medido = st.selectbox(
            "Até onde este ensaio mediu?",
            GRAUS,
            help="Deixe vazio se o ensaio mediu a IDA (produto -> aparelho), que "
                 "é o caso de todos os 177 do caderno. Preencha quando tiver "
                 "medido a VOLTA (aparelho -> vpad -> JOGO): sem esta palavra o "
                 "ensaio não sustenta `O JOGO RECEBEU` nem `O JOGO REAGIU`.",
        )
        # ENSAIO-QUE-NAO-DIZ-A-PONTE-01 (20/08/2026). Irmã da de cima, e do
        # mesmo dia: o `degrau` diz ATÉ ONDE a medição foi, e esta diz POR ONDE
        # ela chegou — máscara DualSense, máscara Xbox, nativo, ou Steam Input.
        # As opções vêm de `PONTES`, que vem da `ESCADA`; nunca redigitadas.
        #
        # O padrão é VAZIO e continua sendo: nenhum dos 177 ensaios do caderno
        # declara a ponte, e vazio quer dizer "não declarou", que é a verdade
        # sobre eles. O que vazio NÃO quer dizer é "serve para toda ponte" — se
        # quisesse, o ensaio de acender lightbar pelo hidraw, sem jogo e sem
        # vpad no meio, sustentaria afirmação sobre a ponte que desse na
        # telha. A regra que separa os dois casos está no
        # `eliminacao.sustentam_a_ponte`.
        ponte_medida = st.selectbox(
            "Por qual ponte este ensaio mediu?",
            PONTES,
            help="Deixe vazio se o ensaio falou direto com o aparelho (hidraw, "
                 "sem jogo e sem vpad no meio), que é o caso dos 177 do "
                 "caderno. Preencha quando houver um JOGO do outro lado: a "
                 "ponte é a máscara/modo por onde ele recebeu.",
        )
        # PECA da cura de 13/08/2026: o `Resultado` acima responde pelo SUSPEITO
        # da linha, e há ensaio em que as duas respostas são OPOSTAS sem que
        # nenhuma esteja errada — o `gatilho-lado-nao-esta-invertido` eliminou o
        # suspeito ("não obedece") na mesma rodada em que o R2 endureceu. Vazio é
        # o padrão e quer dizer "o Resultado também responde pela feature"; é
        # assim que 76 dos 77 ensaios continuam válidos sem ninguém tocá-los.
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
                    # ENSAIO-QUE-NAO-DIZ-O-DEGRAU-01 (20/08/2026): o ensaio passa
                    # a DIZER o que mediu. Vazio quer dizer "não declarou", nunca
                    # "serve para tudo" — e por isso os dois degraus de ENTRADA
                    # exigem que ele venha preenchido. O que sai daqui é o valor
                    # escolhido no formulário; as opções vêm de `VALORES_DA_ESCADA`,
                    # nunca redigitadas.
                    "degrau": degrau_medido,
                    # ENSAIO-QUE-NAO-DIZ-A-PONTE-01 (20/08/2026): ao lado do
                    # `degrau`, porque é o mesmo tipo de eixo — ele diz até onde
                    # a medição foi, esta diz por onde ela chegou. Vazio quer
                    # dizer "não declarou", nunca "serve para toda ponte"; as
                    # opções vêm da `ESCADA`, nunca redigitadas.
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
