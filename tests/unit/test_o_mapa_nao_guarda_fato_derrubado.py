"""O mapa de canais não pode guardar VIVO um fato que esta casa já derrubou.

O DEFEITO QUE ESTE ARQUIVO EXISTE PARA PEGAR
--------------------------------------------
Medido em 02/09/2026, com três historiadores lendo os commits, os 178 ensaios do
caderno e os estudos: **o mapa carregava quarenta células cuja prosa uma medição
posterior desta mesma casa já tinha derrubado**, e as duas réguas do arquivo
estavam VERDES o tempo todo.

Isso não é falha das duas réguas — é o alcance delas. O
`scripts/check_paridade_transporte.py` cobra que exista teste, que exista ensaio
e que o valor caia no domínio; o `scripts/validar-caducos.py` cobra um literal
por vez, e só nas superfícies vivas (README, docs/usage, docs/protocol, src,
po), onde `docs/data/` não entra. **Nenhuma das duas pergunta se a PROSA ainda é
verdade.** A classe inteira do defeito passava sem régua.

A FORMA QUE MAIS CUSTOU, e é ela que este portão mede
------------------------------------------------------
Não é a célula que diz uma coisa errada — é a célula que diz a coisa errada
**colada na medição que a derruba**. Dois casos medidos naquele dia:

- `gatilho.adaptativo@dualsense` dizia `NINGUEM MEDIU ISSO` e, na frase
  seguinte, `A PREVISAO HERDADA FOI MEDIDA, E CAIU — 11/08/2026`. As duas
  afirmações, na mesma célula, em SEIS células iguais (os dois lados de três
  linhas irmãs). Quem lesse metade levava a versão derrubada.
- `luz.lightbar.cor@dualsense` dizia, no `radio_evidencia`, que a reconexão CURA
  e que a causa é a instância de conexão; a célula vizinha, `radio_ressalva`,
  dizia que isso NÃO está provado e que o juiz devolve CONFUSO.

**Uma linha que se contradiz é pior que uma linha errada.**

A REGRA, E POR QUE ELA É ESTA
------------------------------
A regra da casa é *"não se apaga decisão medida — ela ganha nota datada; MAS
FATO ERRADO SE SUBSTITUI, e sai de TODOS os lugares onde aparece"*. Substituir,
nesta casa, é escrito num formato: a célula nomeia a frase que caiu, diz quando
caiu e quem a derrubou. O mapa já usa esse formato em dezenas de células
(`SUBSTITUÍDO em 14/08/2026: …`, `FATO ERRADO SUBSTITUÍDO`, `caducou em 19/07`).

Então o contrato deste portão é:

    a frase derrubada só pode aparecer DEPOIS da marca que a enterra,
    na mesma célula e dentro de uma janela curta.

Sem a marca antes, a frase está VIVA — e é isso que reprova. Com a marca antes,
ela é citação de registro histórico, que é exatamente o que a casa manda
preservar.

**A ORDEM É O CONTRATO, e ela custou uma versão deste portão.** A primeira
tentativa aceitava a marca em qualquer lugar da célula, e a MORDIDA a derrubou
na hora: com a cura arrancada, `gatilho.adaptativo@dualsense` voltou a dizer
`NINGUEM MEDIU ISSO. A PREVISAO HERDADA FOI MEDIDA, E CAIU` — a frase morta na
frente, a marca atrás — e o portão passou VERDE, porque achou o `E CAIU`. É a
forma exata do defeito que ele existe para pegar, e ele não a via. Quem enterra
anuncia primeiro e cita depois; quem afirma primeiro está afirmando.

**Por que não apagar a frase de vez e dispensar a marca:** porque o mapa é
memória externa. Uma frase que sumiu sem rastro volta pela mão de quem não sabe
que ela já caiu — foi assim que o *"até o power-off físico"* de julho migrou de
`luz.lightbar.cor` para `luz.lightbar.aviso_de_modo` em 19/08/2026, quatro
meses depois de falso. Um fato errado parado no repositório **recruta**.

O QUE ESTE PORTÃO NÃO É
------------------------
Não é uma régua de verdade universal: ele não sabe se uma frase qualquer é
verdadeira. Ele guarda uma LISTA NOMEADA de fatos que a bancada desta casa já
derrubou, cada um com a data e o que o derrubou. **Quem derrubar um fato novo
acrescenta a linha aqui** — é o mesmo gesto de escrever no `caducos.csv`, e
custa o mesmo.

Não é redundância do `validar-caducos.py`: aquele varre as superfícies vivas do
produto atrás de um literal; este varre as 15.400 células do mapa atrás de uma
frase que precisa vir enterrada. Alvos diferentes, contratos diferentes.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

#: As marcas com que esta casa ENTERRA um fato. Sair de qualquer uma delas é
#: sair do formato que o próprio mapa já usa — não é vocabulário inventado
#: aqui: `SUBSTITUÍDO em 14/08/2026`, `FATO ERRADO SUBSTITUÍDO`,
#: `caducou em 19/07`, `REFUTADA por medição em 03/08` e `E CAIU — 11/08/2026`
#: são todas frases que já estavam no CSV antes deste portão existir.
#:
#: `CORRIGID` entrou em 02/09/2026, na segunda rodada de curadoria: o mapa já
#: usava as duas palavras como sinônimas para o mesmo gesto — `CORREÇÃO DE
#: FATO` é o vocabulário do próprio `CLAUDE.md` —, e metade das células que a
#: rodada enterrou tinha sido escrita com ela. Ampliar a lista é o oposto de
#: afrouxar o portão: sem `CORRIGID` ele reprovaria a célula CURADA e
#: continuaria cego à podre.
MARCA_DE_SEPULTAMENTO = re.compile(
    r"SUBSTITU|FATO ERRADO|caduc|REFUTAD|derrubad|CORRIGID|"
    r"E CAIU|caíram|CAIU EM|deixou de valer|SAIU em \d",
    re.IGNORECASE,
)

#: Quantos caracteres a marca pode ficar ANTES da frase morta. Curto de
#: propósito: a marca tem de estar na vizinhança da citação, não em outro
#: parágrafo da mesma célula falando de outro fato — foi assim que a primeira
#: versão deste portão passou verde com a cura arrancada.
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
            "src/hefesto_dualsense4unix/daemon/ipc_handlers.py:2820-2827"
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
    # ------------------------------------------------------------------
    # SEGUNDA RODADA DE CURADORIA — 02/09/2026. Seis historiadores
    # confrontaram o mapa com o CÓDIGO do produto (a primeira rodada tinha
    # lido commits, ensaios e estudos). O que muda de fonte muda de forma: a
    # primeira achou prosa que outra medição derrubou; esta achou prosa que o
    # próprio `src/` desmente. As oito abaixo são as que RECRUTAM — a frase é
    # afirmativa, distinta e convincente, e quem a lesse sairia com o
    # diagnóstico errado.
    # ------------------------------------------------------------------
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
            "o produto o LÊ desde a MIC-DA-MESA-ELEICAO-01: `extract_jack_status`"
            " → `_registrar_borda_do_mic` → `bordas_do_mic` → `mic_da_mesa_loop`,"
            " nos dois transportes. A linha irmã `audio.jack.deteccao@dualsense` "
            "sempre disse que o bit2 desse byte é o MIC_MUTE"
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
    # ------------------------------------------------------------------
    # TERCEIRA RODADA — 03/09/2026, a leva que varreu o código atrás de
    # filtro NOSSO de transporte (*"o que no código tá setado pra funcionar
    # só via cabo e não BT"*). A área da MESA achou o defeito na forma que
    # esta casa mais paga: a correção PELA METADE. O endereço certo entrou
    # numa célula em 02/09 e as três irmãs ficaram com o velho.
    # ------------------------------------------------------------------
    Derrubado(
        nome="o `slot_for` mora em `identity.py:543`",
        padrao=re.compile(r"identity\.py:543"),
        caiu_em="02/09/2026, e só metade saiu",
        quem_derrubou=(
            "`:543` é o comentário de `self._external_present` (presença de "
            "controle EXTERNO, que é outro eixo); o `slot_for` é "
            "src/hefesto_dualsense4unix/daemon/subsystems/identity.py:668. A "
            "troca entrou em 02/09 só na `nota` de "
            "`combinacao.slot_jogador.estabilidade@dualsense` e deixou vivas as "
            "duas irmãs (@pro, @sn30) e as DUAS células de código de "
            "`plataforma.slot_jogador@dualsense` — que é o endereço que o "
            "`specs.html` publica para quem for procurar o slot no código"
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
    """As células que afirmam um fato derrubado sem a marca que o enterra.

    Uma ocorrência conta como enterrada quando alguma marca a PRECEDE dentro de
    `JANELA` caracteres. Basta UMA ocorrência solta para a célula reprovar.
    """
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
    """A MORDIDA: um mapa de mentira com a frase morta SOLTA tem de reprovar.

    Sem isto o portão seria verde por não achar nada, que é a forma exata do
    instrumento falso que esta casa já pegou cinco vezes num dia só.
    """
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
    """E o contrário: com a marca, a mesma frase é registro, não afirmação.

    É a metade que impede o portão de proibir a memória — apagar a frase de vez
    é o que faz um fato errado voltar pela mão de quem não soube que ele caiu.
    """
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
    """A ORDEM É O CONTRATO — e foi a mordida que provou que ela precisa ser.

    Este é o caso literal de `gatilho.adaptativo@dualsense` antes da cura de
    02/09/2026: a frase morta na frente, a refutação atrás. A primeira versão
    deste portão aceitava isso e ficava verde com a cura arrancada.
    """
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
