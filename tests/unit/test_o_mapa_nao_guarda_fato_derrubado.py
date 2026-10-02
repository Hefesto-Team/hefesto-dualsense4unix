"""O mapa de canais não pode guardar VIVO um fato que esta casa já derrubou."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

MARCA_DE_SEPULTAMENTO = re.compile(
    r"SUBSTITU|FATO ERRADO|caduc|REFUTAD|derrubad|CORRIGID|"
    r"E CAIU|caíram|CAIU EM|deixou de valer|SAIU em \d",
    re.IGNORECASE,
)

JANELA = 600


@dataclass(frozen=True)
class Derrubado:
    """Um fato que a bancada desta casa mediu e derrubou."""

    nome: str
    padrao: re.Pattern[str]
    caiu_em: str
    quem_derrubou: str


FATOS_DERRUBADOS: tuple[Derrubado, ...] = (
    Derrubado(
        nome="o latch da lightbar por rádio dura até o POWER-OFF FÍSICO",
        padrao=re.compile(
            r"persistindo até o POWER-OFF"
            r"|desfeito pelo POWER-OFF"
            r"|apagada até o power-off"
            r"|kernel até o power-off",
            re.IGNORECASE,
        ),
        caiu_em="09/08/2026",
        quem_derrubou=(
            "um restart do daemon repinta (medido por ela), e os ensaios "
            "`lightbar-bt-aceso-0808-1639`, `-0808-2135`, `-0808-2348` e "
            "`-1108-1140` do caderno mostram a barra acesa no rádio sem "
            "power-off nenhum"
        ),
    ),
    Derrubado(
        nome="a faixa de feature reports do aparelho nunca foi varrida",
        padrao=re.compile(
            r"NÃO TENTADO: varrer a faixa de feature reports"
            r"|A varredura de feature reports nunca foi feita"
            r"|nenhuma varredura desse tipo está registrada nesta casa"
            r"|ligar ou desligar a IMU, ninguém procurou",
            re.IGNORECASE,
        ),
        caiu_em="15/08/2026",
        quem_derrubou=(
            "os 17 ids que o descritor do rádio declara foram lidos nos quatro "
            "DualSense, e a união de 24 ids foi pedida aos quatro nos DOIS "
            "transportes às 19h26; ver docs/protocol/"
            "dualsense-referencia-canonica.md, o censo dos dezessete"
        ),
    ),
    Derrubado(
        nome=(
            "ninguém mediu se o keepalive apaga o efeito de gatilho de terceiro"
        ),
        padrao=re.compile(r"NINGUEM MEDIU ISSO|NINGUÉM MEDIU ISSO"),
        caiu_em="11/08/2026",
        quem_derrubou=(
            "um `rigid(3,8)` cru, por fora do daemon, com o daemon vivo e o "
            "código NÃO curado, sobreviveu a 8 s e a 30 s — ensaios "
            "`gatilho-keepalive-8s` e `gatilho-keepalive-30s` no caderno"
        ),
    ),
    Derrubado(
        nome="a gramática do byte [2] do output 0x32 nunca foi medida",
        padrao=re.compile(
            r"nenhuma delas foi medida|e nenhuma foi medida",
            re.IGNORECASE,
        ),
        caiu_em="15/08/2026",
        quem_derrubou=(
            "o `scripts/ensaios/corpo_do_0x32.py` mediu nas duas unidades do "
            "rádio às 21h36, com controle positivo e negativo, e devolveu TLV "
            "nas duas — bruto em docs/data/ensaios-brutos/"
            "2026-08-15-E1-corpo-do-0x32.txt"
        ),
    ),
    Derrubado(
        nome="o CRC-32 do envelope de rádio tem TRÊS sementes",
        padrao=re.compile(r"TRÊS sementes"),
        caiu_em="27/08/2026",
        quem_derrubou=(
            "são QUATRO: o A/B no aparelho, mesmo controle e mesmo comando, deu "
            "errno 5 para 0xA3 e para 0xA2 e ACEITOU o 0x53 "
            "(SET_REPORT|FEATURE) — ensaio `cor-do-plastico-radio-e7`"
        ),
    ),
    Derrubado(
        nome="o `state_full` publica `coop.players` como número, não como lista",
        padrao=re.compile(
            r"`coop\.players` (?:e|é) um NÚMERO, não uma lista"
            r"|`coop\.players` como um NÚMERO, não como lista",
        ),
        caiu_em="15-16/08/2026",
        quem_derrubou=(
            "o QUEM-É-QUEM-01 publicou `coop.mesa`, uma lista sempre presente "
            "que casa o físico com o vpad — "
            "src/hefesto_dualsense4unix/daemon/ipc_handlers.py:2140-2147"
        ),
    ),
    Derrubado(
        nome="nenhum aparelho trocou de braço em 15/08",
        padrao=re.compile(r"nenhum aparelho trocou de braço", re.IGNORECASE),
        caiu_em="15/08/2026, 19h",
        quem_derrubou=(
            "ela inverteu os braços à mão e as medições rodaram de novo às "
            "19h32, com os quatro aparelhos passando pelos dois transportes — "
            "bruto em docs/data/ensaios-brutos/"
            "2026-08-15-TROCA-DE-BRACOS-taxa-e-0x22-depois.txt"
        ),
    ),
    Derrubado(
        nome="os ~797 Hz do rádio são pico INSTANTÂNEO dentro da rajada",
        padrao=re.compile(
            r"pico instantâneo de ~?797|taxa INSTANTÂNEA dentro da rajada",
            re.IGNORECASE,
        ),
        caiu_em="23/08/2026",
        quem_derrubou=(
            "medido pelo relógio do próprio sensor: ~800 rel/s é o ORÇAMENTO DO "
            "ADAPTADOR, repartido entre os controles que ele hospeda (796,8 e "
            "800,8 Hz sozinho; 398,3 e 400,2 Hz dividindo)"
        ),
    ),
    Derrubado(
        nome="a reconexão CURA a lightbar travada por rádio",
        padrao=re.compile(r"A RECONEXAO CURA|A RECONEXÃO CURA", re.IGNORECASE),
        caiu_em="12/08/2026",
        quem_derrubou=(
            "o `scripts/eliminacao.py` devolve CONFUSO para o suspeito, e ela "
            "parou o registro antes de virar fato: reconectar cura já tinha "
            "caído quatro vezes nesta frente"
        ),
    ),
    Derrubado(
        nome="o driver do Pro envia CINCO comandos JC_USB_CMD_*",
        padrao=re.compile(r"NO_TIMEOUT 0x04, EN_TIMEOUT 0x05"),
        caiu_em="31/08/2026",
        quem_derrubou=(
            "são QUATRO: `JC_USB_CMD_EN_TIMEOUT` aparece uma única vez em "
            "assets/dkms/hid-nintendo/hid-nintendo.c — o #define em :172 — e "
            "não é enviado por barramento nenhum"
        ),
    ),
    Derrubado(
        nome="a escada do mapa não tem degrau para o jogo",
        padrao=re.compile(
            r"não tem degrau para O JOGO RECEBEU"
            r"|Os dois degraus que faltam",
        ),
        caiu_em="19/08/2026, 11h58",
        quem_derrubou=(
            "`O JOGO RECEBEU` e `O JOGO REAGIU` entraram em `ESCADA` no mesmo "
            "dia em que a nota foi escrita, com as regras 13 e 14 do "
            "scripts/check_paridade_transporte.py"
        ),
    ),
    Derrubado(
        nome="a única rota de LED de jogador por rádio é o sysfs",
        padrao=re.compile(
            r"ÚNICA rota: sysfs"
            r"|A rota hidraw é suprimida incondicionalmente"
            r"|SÓ o sysfs\. Por Bluetooth a rota da pydualsense",
            re.IGNORECASE,
        ),
        caiu_em="12/08/2026",
        quem_derrubou=(
            "a ROTA-BT-EM-REGIME-01 criou a SEGUNDA rota: o report 0x31 avulso "
            "escrito no hidraw, com o bit PLAYER_INDICATOR e o common[43] — "
            "`_pintar_por_hidraw_bt`, chamado pelo `_for_each_led` FORA do "
            "`if node is not None`. O que segue suprimido por rádio é só o "
            "fallback da pydualsense dentro do report_thread"
        ),
    ),
    Derrubado(
        nome="nenhum report de ENTRADA devolve o mudo de firmware do microfone",
        padrao=re.compile(
            r"nenhum report de ENTRADA conhecido devolve volume, rota, "
            r"pré-amp ou o mudo de firmware",
            re.IGNORECASE,
        ),
        caiu_em="01/09/2026",
        quem_derrubou=(
            "o mudo VOLTA no bit 0x04 de payload[53] — o mesmo byte do jack — e "
            "o produto o LÊ desde a MIC-DA-MESA-ELEICAO-01 (hoje pelo "
            "`extract_estado_do_mic`, junto do botão, que é o gesto desde "
            "28/09), nos dois transportes. A linha irmã "
            "`audio.jack.deteccao@dualsense` sempre disse que o bit2 desse byte "
            "é o MIC_MUTE"
        ),
    ),
    Derrubado(
        nome="`_struct_base` não testa o bit de áudio do report 0x31",
        padrao=re.compile(
            r"`_struct_base` NÃO testa o bit1 de report\[1\]"
            r"|FURO ABERTO \(BT-FURO-FINO-01 defeito 1\)",
        ),
        caiu_em="16/08/2026",
        quem_derrubou=(
            "o PS-PRESO-01 fechou o furo: `if report[1] & INPUT_FLAG_AUDIO: "
            "return None` em core/physical_report_reader.py, com "
            "tests/unit/test_ps_preso_01_audio_lido_como_botao.py verde. A "
            "tranquilização que vinha colada — «inerte só porque a ponte de mic "
            "nasce DESLIGADA» — é a metade mais perigosa: a eleição do "
            "microfone pelo botão entrou em 01/09/2026"
        ),
    ),
    Derrubado(
        nome="o produto não lê o acelerômetro — ABS_X/Y/Z «não entram aqui»",
        padrao=re.compile(
            r"não entram aqui"
            r"|o acelerômetro não é um número — é PASSAGEM",
            re.IGNORECASE,
        ),
        caiu_em="29/08/2026",
        quem_derrubou=(
            "a ONDA-CONTROLES-04 fez o acelerômetro ser LIDO: o laço de "
            "`ABS_X/ABS_Y/ABS_Z` em core/evdev_reader.py, `g_por_unidade`, e o "
            "`SensorHub` publicando `inputs.accel` com três casas "
            "(daemon/sensor_hub.py) até `accel_do_inputs` na tela. A docstring "
            "que a frase citava foi trocada no mesmo dia, e diz o contrário"
        ),
    ),
    Derrubado(
        nome="nenhum ensaio de `entrada.bruta` foi escrito na leva de 15/08",
        padrao=re.compile(
            r"Subir o grau exige ensaio em docs/data/ensaios\.csv, e nenhum "
            r"foi escrito nesta leva",
            re.IGNORECASE,
        ),
        caiu_em="15/08/2026, 22:12",
        quem_derrubou=(
            "OITO ensaios de `entrada.bruta@dualsense` estão no caderno, todos "
            "de 2026-08-15T22:12 com `observado_por = aparelho` — quatro por "
            "cabo e quatro por rádio: `bruta-contador-*` e `bruta-reservados-*`."
            " O teto do grau continua `MONTOU`, mas por outra razão"
        ),
    ),
    Derrubado(
        nome=(
            "o teto do throttle é a única peça do código que reconhece mais de "
            "um controle na mesa"
        ),
        padrao=re.compile(
            r"único lugar da árvore que reconhece que dois controles na mesa"
            r"|única peça do código que reconhece que dois na mesa"
            r"|única peça do produto que reconhece que quatro na mesa",
            re.IGNORECASE,
        ),
        caiu_em="27/06/2026",
        quem_derrubou=(
            "o `daemon/subsystems/coop.py` são 2.004 linhas cuja razão de "
            "existir é exatamente «dois na mesa não é um», e ele faz SAÍDA — "
            "`_apply_coop_player_leds` acende o padrão do jogador de CADA "
            "controle e `_make_player_rumble_sink` roteia rumble por jogador. "
            "Ele nasceu ANTES do índice de 10/08 que a frase cita como origem"
        ),
    ),
    Derrubado(
        nome="o Hefesto não lê o `hardware_version` do sysfs",
        padrao=re.compile(
            r"O Hefesto NÃO lê este nó: `hardware_version` não aparece uma vez",
            re.IGNORECASE,
        ),
        caiu_em="22/08/2026",
        quem_derrubou=(
            "o commit e2c9d401 (BARRA-MUDA-01) criou "
            "integrations/sinal_da_barra.py, cujo `instancias_dualsense` lê o "
            "`hardware_version` de toda conexão viva; o daemon a chama no "
            "hotplug, a janela GTK ao montar a aba, e o valor sai pelo IPC para "
            "a tela — sete dias DEPOIS do «conferido em 15/08/2026» da célula"
        ),
    ),
    Derrubado(
        nome="nenhum DualSense esteve no fio em 15/08, e o lado do cabo é inferência",
        padrao=re.compile(
            r"o cabo continua `inferido-do-código` porque nenhum deles esteve "
            r"no fio neste dia",
            re.IGNORECASE,
        ),
        caiu_em="15/08/2026, 22:12",
        quem_derrubou=(
            "o `cabo_evidencia` da própria linha descreve a mesa 2+2 com dois "
            "controles no fio, `cabo_de_onde_sei` é `medido`, e o caderno tem "
            "quatro ensaios com `transporte = cabo` na mesma hora. A frase era o "
            "estado de ANTES das 22:12 e sobreviveu à subida, do outro lado da "
            "mesma linha"
        ),
    ),
    Derrubado(
        nome="o `slot_for` mora em `identity.py:418`",
        padrao=re.compile(r"identity\.py:543"),
        caiu_em="02/09/2026, e só metade saiu",
        quem_derrubou=(
            "`:543` é o comentário de `self._external_present` (presença de "
            "controle EXTERNO, que é outro eixo); o `slot_for` é "
            "src/hefesto_dualsense4unix/daemon/subsystems/identity.py:464. A "
            "troca entrou em 02/09 só na `nota` de "
            "`combinacao.slot_jogador.estabilidade@dualsense` e deixou vivas as "
            "duas irmãs (@pro, @sn30) e as DUAS células de código de "
            "`plataforma.slot_jogador@dualsense` — que é o endereço que o "
            "`specs.html` publica para quem for procurar o slot no código"
        ),
    ),
    Derrubado(
        nome="o gesto de eleição do microfone é a virada do bit de mudo",
        padrao=re.compile(
            r"é ele que dá o sujeito do gesto"
            r"|mascara `STATUS_MIC_MUDO` e conta BORDAS",
        ),
        caiu_em="28/09/2026",
        quem_derrubou=(
            "a O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01: o bit de mudo vira com "
            "qualquer um que escreva o mudo no firmware (três bordas que ela "
            "não deu, no branco, na sessão de 28/09); o gesto passou a ser o "
            "botão (`buttons[2]` bit 2), lido com o `status[1]` do mesmo "
            "report por `extract_estado_do_mic`"
        ),
    ),
    Derrubado(
        nome="a borda do microfone exige sustentação (`SUSTENTACAO_DO_MUDO_S`)",
        padrao=re.compile(
            r"CURA APLICADA: a borda passa a exigir SUSTENTA"
            r"|SUSTENTACAO_DO_MUDO_S",
        ),
        caiu_em="28/09/2026",
        quem_derrubou=(
            "a O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01: a sustentação de 300 ms "
            "olhava a virada do bit, e o gesto passou a ser o botão, que nem o "
            "gating do rádio nem o eco da nossa escrita apertam; a constante "
            "saiu do `core/backend_pydualsense.py`"
        ),
    ),
)


def celulas(caminho: Path | str) -> list[tuple[str, str, str]]:
    """`(id, coluna, texto)` de toda célula não vazia do mapa."""
    texto = Path(caminho).read_text(encoding="utf-8")
    saida: list[tuple[str, str, str]] = []
    for linha in csv.DictReader(texto.splitlines()):
        alvo = linha.get("id") or "?"
        for coluna, valor in linha.items():
            if valor:
                saida.append((alvo, coluna, valor))
    return saida


def _enterrada(valor: str, inicio: int) -> bool:
    """Há marca de sepultamento ANTES da posição `inicio`, dentro da janela?"""
    antes = valor[max(0, inicio - JANELA) : inicio]
    return MARCA_DE_SEPULTAMENTO.search(antes) is not None


def vivos(caminho: Path | str) -> list[tuple[Derrubado, str, str]]:
    """As células que afirmam um fato derrubado sem a marca que o enterra."""
    achados: list[tuple[Derrubado, str, str]] = []
    for alvo, coluna, valor in celulas(caminho):
        for fato in FATOS_DERRUBADOS:
            if any(
                not _enterrada(valor, m.start())
                for m in fato.padrao.finditer(valor)
            ):
                achados.append((fato, alvo, coluna))
    return achados


def test_nenhum_fato_derrubado_esta_vivo_no_mapa() -> None:
    """Nenhuma célula afirma, sem enterrar, algo que a bancada já derrubou."""
    achados = vivos(MAPA)
    if achados:
        recado = "\n".join(
            f"  {alvo} · {coluna}\n"
            f"      caiu em {fato.caiu_em}: {fato.nome}\n"
            f"      quem derrubou: {fato.quem_derrubou}"
            for fato, alvo, coluna in achados
        )
        pytest.fail(
            f"{len(achados)} célula(s) do mapa afirmam um fato derrubado sem a "
            f"marca que o enterra (SUBSTITUÍDO / FATO ERRADO / caducou / "
            f"REFUTADA / derrubada). A regra da casa é que fato errado SAI, e "
            f"que a substituição diga o que caiu, quando e por quê:\n" + recado
        )


def test_a_lista_de_fatos_derrubados_nao_esta_vazia() -> None:
    """Portão sem alvo é portão desligado — e já aconteceu nesta casa."""
    assert FATOS_DERRUBADOS, "a lista de fatos derrubados ficou vazia"
    for fato in FATOS_DERRUBADOS:
        assert fato.caiu_em, f"{fato.nome}: sem data de queda"
        assert fato.quem_derrubou, f"{fato.nome}: sem quem derrubou"


def test_a_regua_morde_um_fato_derrubado_solto(tmp_path: Path) -> None:
    """A MORDIDA: um mapa de mentira com a frase morta SOLTA tem de reprovar."""
    mentira = tmp_path / "mapa.csv"
    mentira.write_text(
        "id,radio_detalhe\n"
        "luz.lightbar.cor@dualsense,"
        '"a barra ignora as escritas do kernel, persistindo até o POWER-OFF '
        'FÍSICO."\n',
        encoding="utf-8",
    )
    achados = vivos(mentira)
    assert len(achados) == 1, "a régua não viu a frase morta solta"
    assert achados[0][0].caiu_em == "09/08/2026"


def test_a_regua_aceita_a_mesma_frase_quando_ela_vem_enterrada(
    tmp_path: Path,
) -> None:
    """E o contrário: com a marca, a mesma frase é registro, não afirmação."""
    honesta = tmp_path / "mapa.csv"
    honesta.write_text(
        "id,radio_detalhe\n"
        "luz.lightbar.cor@dualsense,"
        '"FATO ERRADO SUBSTITUÍDO em 02/09/2026: dizia que a barra ignora as '
        'escritas do kernel, persistindo até o POWER-OFF FÍSICO. Falso desde '
        '09/08/2026 — um restart do daemon repinta."\n',
        encoding="utf-8",
    )
    assert vivos(honesta) == []


def test_a_marca_depois_da_frase_nao_enterra_nada(tmp_path: Path) -> None:
    """A ORDEM É O CONTRATO — e foi a mordida que provou que ela precisa ser."""
    torta = tmp_path / "mapa.csv"
    torta.write_text(
        "id,cabo_ressalva\n"
        "gatilho.adaptativo@dualsense,"
        '"NINGUEM MEDIU ISSO. A PREVISAO HERDADA FOI MEDIDA, E CAIU — '
        '11/08/2026."\n',
        encoding="utf-8",
    )
    achados = vivos(torta)
    assert len(achados) == 1, "a marca DEPOIS da frase não pode enterrá-la"
