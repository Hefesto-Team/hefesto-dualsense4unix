"""O caminho do RÁDIO de vibração e gatilhos, e a régua que o segura no lugar.

Levantamento de 03/09/2026, sobre o pedido dela: *"ver o que no código tá setado
pra funcionar só via cabo e não BT (…) e verificar no specs o caminho do Bt pra
garantir que lá ele possa funcionar em ambos os modos"*.

**O QUE A VARREDURA ACHOU, e é um negativo que vale escrever:** na área de
vibração e gatilhos do DualSense **não há filtro nosso** — nenhum `if` de
transporte, nenhuma exigência de barramento, nenhuma variável de ambiente,
nenhuma declaração no `maquina.json`. O único ponto do produto que sabe o
transporte é a ESCOLHA DO ENVELOPE (`prepareReport`), e ela é uma linha. O
filtro que existia morreu na BTREPORT-02, e era o pior tipo: o 0x31 da
pydualsense 0.7.5 é malformado, o firmware o descartava, e todo o nosso output
por rádio — rumble, gatilhos, keepalive — era no-op **sem uma linha de erro**.

Um negativo desses apodrece calado: a próxima pessoa que precisar de um ramo
por transporte vai escrevê-lo dentro do caminho comum, e ninguém vai notar. As
quatro primeiras réguas daqui são o que impede isso.

**O QUE FOI ESCRITO NO MAPA, e é o que as demais réguas seguram:**

* `vibracao.haptics_vcm@dualsense` — o `radio_offset` dizia «não localizado» e
  passou a trazer DOIS candidatos de arranjo do bloco háptico dentro do degrau
  0x39, com repositório, commit e arquivo:linha, e a divergência entre eles
  registrada em vez de resolvida. O place holder da tag (`BLOCO_HAPTICS = 0x12`)
  já existia declarado e sem uso — é ele que o mapa passou a citar;
* `gatilho.leitura@dualsense` — o `cabo_offset` dizia «não localizado» enquanto
  a célula IRMÃ da mesma linha já dava a resposta; e o `radio_canal` dizia
  `outro` para um report que este produto abre e decodifica por `/dev/hidrawN`
  todo quadro;
* as QUATRO linhas de rumble por motor do Pro e do SN30 estavam MUDAS nas duas
  colunas de transporte, com o caminho inteiro no fonte que esta árvore
  versiona (`assets/dkms/hid-nintendo/hid-nintendo.c`).

**A MORDIDA de cada régua está escrita no docstring dela.** Nenhuma delas
afirma que o aparelho obedeceu: o teto do que este levantamento pode dizer é
MONTOU, e as réguas cobram exatamente isso — inclusive a que reprova se alguém
promover o háptico a `medido` sem bancada.
"""

from __future__ import annotations

import ast
import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
NINTENDO = RAIZ / "assets" / "dkms" / "hid-nintendo" / "hid-nintendo.c"
MODPROBE = RAIZ / "assets" / "modprobe.d" / "hefesto-hid-nintendo.conf"
BT_AUDIO = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "dualsense_bt_audio.py"
)
BACKEND = RAIZ / "src" / "hefesto_dualsense4unix" / "core" / "backend_pydualsense.py"
LEITOR = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "core" / "physical_report_reader.py"
)
RUMBLE_SUB = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "subsystems" / "rumble.py"
)
RUMBLE_CORE = RAIZ / "src" / "hefesto_dualsense4unix" / "core" / "rumble.py"

csv.field_size_limit(10**9)


def _linhas() -> dict[str, dict[str, str]]:
    with MAPA.open(encoding="utf-8", newline="") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


@pytest.fixture(scope="module")
def mapa() -> dict[str, dict[str, str]]:
    return _linhas()


# --------------------------------------------------------------------------
# 1. O caminho comum NÃO ramifica por transporte
# --------------------------------------------------------------------------

#: As palavras que só aparecem em quem PERGUNTA o transporte. `bt`/`usb` entram
#: com fronteira de palavra: `_bt_seq` (o contador de sequência do envelope) não
#: é pergunta de transporte, e cair nele seria falso positivo.
_PERGUNTAS_DE_TRANSPORTE = (
    r"\bconType\b",
    r"\bConnectionType\b",
    r"\b_detect_transport\b",
    r"\bget_transport\b",
    r"\bself\._transport\b",
    r"\bBUS_BLUETOOTH\b",
    r"[\"']bt[\"']",
    r"[\"']usb[\"']",
)

#: As funções do caminho de VIBRAÇÃO e GATILHO no backend. Nenhuma delas pode
#: perguntar o transporte: o payload é idêntico nos dois, e quem escolhe o
#: envelope é `prepareReport`, que fica de fora desta lista de propósito.
_FUNCOES_SEM_TRANSPORTE = (
    "_build_common",
    "set_rumble",
    "set_rumble_for",
    "set_trigger",
    "force_rumble_stop",
    "_escalar_rumble",
)


def _fonte_das_funcoes(caminho: Path, nomes: tuple[str, ...]) -> dict[str, str]:
    texto = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(texto)
    achadas: dict[str, str] = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef) and no.name in nomes:
            achadas[no.name] = ast.get_source_segment(texto, no) or ""
    return achadas


def test_o_payload_de_vibracao_e_gatilho_nao_pergunta_o_transporte() -> None:
    """Nenhuma função do caminho comum ramifica por cabo/rádio.

    O `common` de 47 bytes é IDÊNTICO nos dois transportes — motores em
    `common[2]`/`common[3]`, os dois blocos de gatilho em `common[10..20]` e
    `common[21..31]` — e só o envelope muda. Uma pergunta de transporte dentro
    destas funções é, por construção, um filtro nosso: a diferença que ela
    introduziria não existe no aparelho.

    Mordida: pôr `if self.conType == ConnectionType.BT:` dentro de
    `_build_common` — esta régua reprova, e nomeia a função.
    """
    fontes = _fonte_das_funcoes(BACKEND, _FUNCOES_SEM_TRANSPORTE)
    faltando = set(_FUNCOES_SEM_TRANSPORTE) - set(fontes)
    assert not faltando, (
        f"funções do caminho de vibração/gatilho sumiram do backend: {sorted(faltando)}"
        " — se foram renomeadas, esta régua tem de acompanhar, senão ela deixa de medir"
    )
    culpadas: list[str] = []
    for nome, fonte in fontes.items():
        for padrao in _PERGUNTAS_DE_TRANSPORTE:
            if re.search(padrao, fonte):
                culpadas.append(f"{nome} pergunta o transporte ({padrao})")
    assert not culpadas, (
        "o caminho comum de vibração/gatilho passou a ramificar por transporte: "
        + "; ".join(culpadas)
        + " — o payload é o mesmo nos dois; quem escolhe o envelope é `prepareReport`"
    )


@pytest.mark.parametrize("fonte_py", [RUMBLE_SUB, RUMBLE_CORE])
def test_os_dois_arquivos_de_rumble_nao_sabem_o_que_e_transporte(fonte_py: Path) -> None:
    """`daemon/subsystems/rumble.py` e `core/rumble.py` são cegos ao transporte.

    Medido em 03/09/2026: ZERO ocorrências de qualquer pergunta de transporte
    nos dois módulos inteiros. Não é acidente — é o que faz a política de
    intensidade, o dono do rumble e o resgate do abandonado valerem igual no
    cabo e no rádio.

    Mordida: escrever `if daemon.controller.get_transport() == "bt": return`
    em `reassert_rumble` — esta régua reprova.
    """
    fonte = fonte_py.read_text(encoding="utf-8")
    achados = [p for p in _PERGUNTAS_DE_TRANSPORTE if re.search(p, fonte)]
    assert not achados, (
        f"{fonte_py.name} passou a perguntar o transporte ({achados}) — os dois módulos "
        "de rumble eram cegos a isso de propósito"
    )


# --------------------------------------------------------------------------
# 2. O rumble por motor do Pro/SN30: o driver decide, o mapa copia
# --------------------------------------------------------------------------

def _fonte_do_driver() -> str:
    return NINTENDO.read_text(encoding="utf-8", errors="replace")


def test_o_driver_ainda_poe_o_direito_em_data_mais_quatro() -> None:
    """`joycon_set_rumble` escreve o DIREITO em `data+4` e o ESQUERDO em `data`.

    É a âncora de que as quatro células de offset do mapa dependem. O
    `rumble_data[8]` viaja em `report[2..9]` (`struct joycon_rumble_output`),
    logo direito = report[6..9] e esquerdo = report[2..5].

    Mordida: trocar os dois `joycon_encode_rumble` de lugar no fonte do driver
    — esta régua reprova, e o mapa fica sabendo antes de publicar o endereço
    errado.
    """
    fonte = _fonte_do_driver()
    assert re.search(
        r"/\* right joy-con \*/\s*\n\s*amp = amp_r[^\n]*\n"
        r"\s*joycon_encode_rumble\(data \+ 4,",
        fonte,
    ), "o bloco do motor DIREITO deixou de escrever em `data + 4`"
    assert re.search(
        r"/\* left joy-con \*/\s*\n\s*amp = amp_l[^\n]*\n"
        r"\s*joycon_encode_rumble\(data,",
        fonte,
    ), "o bloco do motor ESQUERDO deixou de escrever em `data`"
    assert re.search(
        r"struct joycon_rumble_output \{\s*\n\s*u8 output_id;\s*\n"
        r"\s*u8 packet_num;\s*\n\s*u8 rumble_data\[8\];",
        fonte,
    ), "o `joycon_rumble_output` mudou de forma — os offsets do mapa caducaram"
    assert re.search(
        r"joycon_set_rumble\(ctlr,\s*\n\s*effect->u\.rumble\.weak_magnitude,"
        r"\s*\n\s*effect->u\.rumble\.strong_magnitude,",
        fonte,
    ), "`joycon_play_effect` deixou de mandar weak como amp_r (direito)"


_FAIXA_POR_LADO = {"direito": "report[6..9]", "esquerdo": "report[2..5]"}


@pytest.mark.parametrize("controle", ["pro", "sn30"])
@pytest.mark.parametrize("lado", ["direito", "esquerdo"])
def test_o_mapa_poe_cada_motor_do_nintendo_na_faixa_certa(
    mapa: dict[str, dict[str, str]], controle: str, lado: str
) -> None:
    """Cada linha de motor cita a SUA faixa, nos dois transportes, e não a outra.

    As quatro linhas estavam MUDAS até 03/09/2026 — `existe = tem` e todas as
    colunas de caminho vazias. Um par trocado aqui é invisível a olho nu e o
    `specs.html` o publica como fato.

    Mordida: trocar `report[6..9]` por `report[2..5]` numa das células — esta
    régua reprova a linha, o lado e o transporte.
    """
    linha = mapa[f"vibracao.rumble.{lado}@{controle}"]
    minha = _FAIXA_POR_LADO[lado]
    outra = _FAIXA_POR_LADO["esquerdo" if lado == "direito" else "direito"]
    for coluna in ("cabo_offset", "radio_offset"):
        celula = linha[coluna]
        assert minha in celula, (
            f"{linha['id']}.{coluna} perdeu a faixa `{minha}` — é a que o driver "
            "escreve para este motor"
        )
        assert outra not in celula, (
            f"{linha['id']}.{coluna} cita a faixa do OUTRO motor (`{outra}`) — motor "
            "trocado é o defeito que esta régua existe para pegar"
        )
    assert linha["radio_canal"] == "evdev", (
        f"{linha['id']}: o canal por rádio é o mesmo do cabo (evdev/FF_RUMBLE)"
    )
    assert linha["radio_report_id"].startswith("0x10"), (
        f"{linha['id']}: o report de saída do rumble puro é o 0x10, nos dois lados"
    )


# --------------------------------------------------------------------------
# 3. O custo do rádio no Nintendo: do driver E da nossa declaração
# --------------------------------------------------------------------------

def test_o_limitador_por_barramento_e_a_nossa_declaracao_continuam_de_pe() -> None:
    """20 ms por cabo, 60 ms por rádio — e o `skip_tx_on_rate_exceeded=1` é nosso.

    A assimetria de RITMO é do driver e é LIMITAÇÃO REAL (o limitador escolhe
    por `hdev->bus`). O DESCARTE do pacote sem janela segura é DECLARAÇÃO
    NOSSA, no `modprobe.d` que o `install.sh` instala, com o default do módulo
    em 0 (== vanilla, transmite). Ela fica, e a razão é do próprio driver:
    transmitir fora de ritmo derruba o link Bluetooth.

    Mordida: apagar o `skip_tx_on_rate_exceeded=1` da conf, ou mudar 60 para 20
    no driver — esta régua reprova.
    """
    fonte = _fonte_do_driver()
    assert re.search(r"#define\s+JC_SUBCMD_RATE_LIMITER_USB_MS\s+20\b", fonte)
    assert re.search(r"#define\s+JC_SUBCMD_RATE_LIMITER_BT_MS\s+60\b", fonte)
    assert "hdev->bus == BUS_USB ? JC_SUBCMD_RATE_LIMITER_USB_MS" in fonte, (
        "o limitador deixou de escolher por barramento — a assimetria mudou de causa"
    )
    conf = MODPROBE.read_text(encoding="utf-8")
    assert "skip_tx_on_rate_exceeded=1" in conf, (
        "a declaração desta casa saiu do modprobe.d — o mapa a descreve como VIVA "
        "em cinco linhas de vibração"
    )


@pytest.mark.parametrize(
    "alvo",
    [
        "vibracao.rumble.direito@pro",
        "vibracao.rumble.esquerdo@pro",
        "vibracao.rumble.direito@sn30",
        "vibracao.rumble.esquerdo@sn30",
        "vibracao.rumble.ff@pro",
    ],
)
def test_a_razao_do_custo_do_radio_esta_escrita_na_linha(
    mapa: dict[str, dict[str, str]], alvo: str
) -> None:
    """A assimetria do Nintendo é declarada onde ela existe, com os dois números.

    `vibracao.rumble.ff@sn30` já a declarava; `vibracao.rumble.ff@pro` estava
    com a célula VAZIA para o mesmo driver e a mesma conf, e as quatro linhas
    de motor nasceram em 03/09/2026 com ela.

    Mordida: esvaziar a `assimetria_declarada` de qualquer uma das cinco — esta
    régua reprova, e o portão `paridade-transporte` volta a acusar assimetria
    não declarada quando alguém encostar nas colunas de `aciona`.
    """
    texto = mapa[alvo]["assimetria_declarada"]
    for exigido in ("20 ms", "60 ms", "skip_tx_on_rate_exceeded"):
        assert exigido in texto, (
            f"{alvo}.assimetria_declarada perdeu `{exigido}` — é metade da razão"
        )


# --------------------------------------------------------------------------
# 4. O háptico por rádio: o place holder e os dois candidatos
# --------------------------------------------------------------------------

def test_o_place_holder_do_haptico_continua_declarado() -> None:
    """`BLOCO_HAPTICS = 0x12` existe, e é o que o mapa manda usar.

    É o mecanismo que ela descreveu: *"quando colocarmos o caminho certo no
    specs o script original vai fazer uso desse place holder setado"*. A
    constante está declarada desde 25/07/2026 e sem uso; a linha
    `vibracao.haptics_vcm@dualsense` passou a citá-la em 03/09/2026.

    Mordida: apagar a constante — esta régua reprova, e o mapa deixa de apontar
    para o vazio antes de alguém segui-lo.
    """
    arvore = ast.parse(BT_AUDIO.read_text(encoding="utf-8"))
    valores = {
        alvo.id: no.value.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Assign) and isinstance(no.value, ast.Constant)
        for alvo in no.targets
        if isinstance(alvo, ast.Name)
    }
    assert valores.get("BLOCO_HAPTICS") == 0x12, (
        "`BLOCO_HAPTICS = 0x12` saiu de `dualsense_bt_audio.py` — o mapa cita esse "
        "place holder como o caminho do háptico por rádio"
    )


def test_o_mapa_do_haptico_traz_os_dois_candidatos_e_o_place_holder(
    mapa: dict[str, dict[str, str]],
) -> None:
    """O `radio_offset` do háptico não é mais «não localizado», e diz o que sabe.

    Duas fontes externas descrevem o bloco háptico dentro do degrau 0x39 e
    DIVERGEM na posição dele — as duas ficam registradas, sem escolher, que é a
    regra desta casa para fonte que se contradiz.

    Mordida: apagar um dos dois arranjos (ou a citação do place holder) — esta
    régua reprova; devolver a célula para «não localizado» também.
    """
    linha = mapa["vibracao.haptics_vcm@dualsense"]
    offset = linha["radio_offset"]
    # A célula CITA o «não localizado» que ela substituiu (é a lei do fato
    # errado: o que caducou fica dito, com data). O que a régua proíbe é a
    # célula VOLTAR a ser aquilo — daí a comparação com o valor inteiro, e não
    # a busca por substring.
    assert offset.strip() != "não localizado", (
        "o `radio_offset` do háptico voltou a «não localizado» — o arranjo está "
        "levantado em duas fontes, com commit e arquivo:linha"
    )
    for exigido in ("0x39", "0x12", "[12..139]", "[413..542]", "DS5Dongle", "Senshi"):
        assert exigido in offset, (
            f"o `radio_offset` do háptico perdeu `{exigido}` — os DOIS candidatos "
            "viajam juntos, senão a divergência some e sobra uma falsa certeza"
        )
    ref = linha["radio_codigo_ref"]
    assert "dualsense_bt_audio.py:225" in ref and "BLOCO_HAPTICS" in ref, (
        "o `radio_codigo_ref` do háptico deixou de apontar para o place holder"
    )


def test_o_haptico_por_radio_nao_promete_obediencia(
    mapa: dict[str, dict[str, str]],
) -> None:
    """Levantar o arranjo NÃO é medir o aparelho, e o mapa não pode confundir.

    O teto do que este levantamento pode afirmar é MONTOU — nem isso, porque
    ninguém montou um bloco 0x12. `radio_aciona` fica `não`, `radio_canal` fica
    `outro` (a FALÁCIA DO CANAL QUE RESPONDE já foi paga uma vez nesta casa, na
    linha irmã do alto-falante) e o grau não sobe para `medido`.

    Mordida: promover `radio_aciona` para `sim`/`parcial`, ou `radio_de_onde_sei`
    para `medido`, sem ensaio — esta régua reprova.
    """
    linha = mapa["vibracao.haptics_vcm@dualsense"]
    assert linha["radio_aciona"] == "não", (
        "o háptico por rádio passou a `aciona` sem ninguém mandar um bloco 0x12"
    )
    assert linha["radio_de_onde_sei"] != "medido", (
        "o háptico por rádio virou `medido` — leitura de fonte de terceiro não é "
        "medição nesta bancada"
    )
    assert linha["radio_canal"] == "outro", (
        "`radio_canal` do háptico virou `hidraw` — é a FALÁCIA DO CANAL QUE RESPONDE; "
        "o degrau responde, o háptico é que não foi tentado"
    )
    assert linha["radio_por_que_nao_aciona"] == "divida", (
        "o háptico por rádio é DÍVIDA (falta o payload), não recusa do aparelho"
    )


# --------------------------------------------------------------------------
# 5. A leitura do gatilho: as duas bases, e o canal que já está aberto
# --------------------------------------------------------------------------

def test_o_leitor_ainda_resolve_as_duas_bases_do_report_de_entrada() -> None:
    """`_struct_base` continua sendo quem separa base 1 (cabo) de base 2 (rádio).

    É a âncora do `cabo_offset` e do `radio_canal` da linha
    `gatilho.leitura@dualsense`: os dois bytes de status de gatilho moram no
    MESMO report de entrada que este produto já abre e decodifica por
    `/dev/hidrawN` nos dois transportes.

    Mordida: apagar `_struct_base` ou o ramo do 0x31 — esta régua reprova.
    """
    texto = LEITOR.read_text(encoding="utf-8")
    assert "def _struct_base(" in texto
    assert "INPUT_REPORT_BT = 0x31" in texto
    assert "INPUT_REPORT_USB = 0x01" in texto


def test_a_leitura_do_gatilho_tem_endereco_nos_dois_lados(
    mapa: dict[str, dict[str, str]],
) -> None:
    """Os dois lados dizem ONDE o byte está, e o canal é o mesmo dos dois.

    O `cabo_offset` dizia «não localizado» enquanto a célula irmã da mesma
    linha já respondia («No cabo (0x01, base 1) os mesmos campos caem em
    report[42] e report[43]»). O `radio_canal` dizia `outro` para o report que
    o leitor de motion decodifica todo quadro.

    Mordida: devolver o `cabo_offset` para «não localizado», ou o `radio_canal`
    para `outro` — esta régua reprova. E ela NÃO deixa promover `aciona`: o
    consumidor continua não existindo.
    """
    linha = mapa["gatilho.leitura@dualsense"]
    cabo = linha["cabo_offset"]
    assert "report[42]" in cabo and "report[43]" in cabo, (
        "o `cabo_offset` da leitura de gatilho perdeu o endereço (base 1 do 0x01)"
    )
    radio = linha["radio_offset"]
    assert "report[43]" in radio and "report[44]" in radio, (
        "o `radio_offset` da leitura de gatilho perdeu o endereço (base 2 do 0x31)"
    )
    assert linha["cabo_canal"] == "hidraw" and linha["radio_canal"] == "hidraw", (
        "a leitura do gatilho sai do mesmo `/dev/hidrawN` nos dois transportes"
    )
    assert linha["cabo_aciona"] == "não" and linha["radio_aciona"] == "não", (
        "ninguém desta casa lê esses dois bytes ainda — saber o endereço não é ler"
    )
    for lado in ("cabo", "radio"):
        assert linha[f"{lado}_por_que_nao_aciona"] == "divida", (
            f"a leitura do gatilho pelo {lado} é DÍVIDA: o endereço está na mão e o "
            "consumidor não existe"
        )
