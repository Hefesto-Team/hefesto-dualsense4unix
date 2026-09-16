"""AS QUATRO PERNAS — toda escolha dela tem de sobreviver ao CICLO, não ao clique.

ORDEM DELA, 16/09/2026, depois de três defeitos da mesma família num dia só::

    "O app deveria construir tudo independente de qual jogo ou launcher. Olha
    preciso que se lembre que o app em si vai ser disponibilizado pra outras
    pessoas e é um app que será focado pra acessibilidade. Isso não pode se
    repetir. Por isso a briga com o sackboy e demais. Esses erros não podem
    seguir."

OS TRÊS DEFEITOS QUE PAGARAM POR ESTE ARQUIVO — o mesmo erro, três vezes:

===========================  ==========================================
`PERFIL-MANDA-01`            a camada GAME era o topo do merge; o jogo
                             pintava por cima do perfil dela
`SOM-ROTA-02`                a rota do alto-falante nunca era escrita na
                             adoção, e o default do firmware é o fone
                             vazio — o som nascia mudo em todo controle
`SOM-ROTA-03`                o gancho do replug exigia a seção `speaker`
                             GLOBAL, e os perfis dela guardam o som por
                             PEÇA — a escolha não voltava do replug
===========================  ==========================================

**Nenhuma régua desta casa perguntava se a escolha dela sobrevive a um CICLO
COMPLETO.** Cada um dos três foi curado como instância, e o quarto apareceria.
Este arquivo pergunta pela CLASSE.

POR QUE ISTO É ACESSIBILIDADE, E NÃO CAPRICHO
----------------------------------------------
Um defeito que exige que a pessoa saiba reaplicar não é inconveniência: quem
depende do controle para jogar não diagnostica *"a rota do `common[7]` não foi
escrita"*. O som não sai, e a conclusão é que o app não funciona. **Falha que
a pessoa não pode nomear é falha total.**

AS QUATRO PERNAS DE CADA CAMPO
-------------------------------
1. **aplica** quando o perfil ativa — já vigiada por
   `test_toda_secao_de_perfil_tem_quem_a_aplique.py`, e é dela que este arquivo
   importa a lista de campos: **uma fonte só, nunca duas**;
2. **volta** depois de desconectar e reconectar o controle;
3. **resiste** quando o jogo (ou o Proton) escreve por cima;
4. **não depende** de qual jogo, qual lançador, nem de haver perfil ativo.

A DÍVIDA É DECLARADA, E ESSE É O DESENHO
-----------------------------------------
Hoje a maioria dos campos NÃO tem as quatro. Uma régua que reprovasse tudo de
uma vez pararia o repositório e seria desligada na semana seguinte — que é como
morrem as réguas honestas demais. Então: **dívida declarada com data passa;
dívida não declarada reprova.** Campo novo tem de responder às quatro antes de
entrar, e o número de dívidas não pode crescer.

É o mesmo padrão do `_CITACOES_PENDENTES` e do `APOSENTADOS` desta casa.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

#: A LISTA DE CAMPOS VEM DA RÉGUA DA PERNA 1, nunca de uma segunda cópia. Ela
#: já é exaustiva contra `Profile.model_fields` nos dois sentidos — campo novo
#: sem classificação reprova lá, e aqui reprova por tabela.
from tests.unit.test_toda_secao_de_perfil_tem_quem_a_aplique import _CLASSIFICACAO

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"


# --------------------------------------------------------------------------
# O vocabulário das respostas
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Cumprida:
    """A perna está de pé, e AQUI está o código que a sustenta.

    `onde` é `caminho/relativo.py::simbolo`. O símbolo é conferido no fonte —
    citação que não abre no que promete é a armadilha nº 1 desta casa.
    """

    onde: str
    como: str


@dataclass(frozen=True)
class NaoSeAplica:
    """A perna não faz sentido para este campo, e a razão diz por quê."""

    razao: str


@dataclass(frozen=True)
class Divida:
    """A perna NÃO está de pé. Declarada, datada, e contada."""

    razao: str
    desde: str


Resposta = Cumprida | NaoSeAplica | Divida

VOLTA = "volta_no_replug"
RESISTE = "resiste_ao_jogo"
INDEPENDE = "independe_do_lancador"
PERNAS = (VOLTA, RESISTE, INDEPENDE)

#: O que o backend devolve sozinho a cada conexão (`_reapply_desired`).
_REAPPLY_DESIRED = (
    "core/backend_pydualsense.py::_reapply_desired",
    "os cinco campos de `_OUTPUT_FIELDS` são reescritos em toda adoção de "
    "handle, no cabo e no rádio, com ou sem perfil ativo",
)
#: A peneira que faz o perfil vencer o jogo (PERFIL-MANDA-01, 16/09/2026).
_PERFIL_MANDA = (
    "core/backend_pydualsense.py::_campos_do_perfil_locked",
    "campo com dono `perfil`/`usuaria` é subtraído do que o jogo manda, nas "
    "três peneiras (entrada, merge e gatilho)",
)
#: Quem não chega ao aparelho não pode perder nem resistir a nada.
_NAO_CHEGA = "não chega ao controle: é metadado do perfil, não estado do aparelho."


_PERNAS: dict[str, dict[str, Resposta]] = {
    # ---------------- o que chega ao controle ----------------
    "triggers": {
        VOLTA: Cumprida(*_REAPPLY_DESIRED),
        RESISTE: Cumprida(*_PERFIL_MANDA),
        INDEPENDE: Cumprida(
            "core/backend_pydualsense.py::_reapply_desired",
            "escreve no hidraw do aparelho; não consulta jogo nem lançador",
        ),
    },
    "leds": {
        VOLTA: Cumprida(*_REAPPLY_DESIRED),
        RESISTE: Cumprida(*_PERFIL_MANDA),
        INDEPENDE: Cumprida(
            "core/backend_pydualsense.py::_reapply_desired",
            "idem gatilhos: o caminho é o report, não o lançador",
        ),
    },
    "speaker": {
        VOLTA: Cumprida(
            "profiles/manager.py::reapply_speaker_on_connect",
            "SOM-ROTA-03 (16/09/2026): o override da PEÇA volta no replug e "
            "vence a global, na mesma ordem que `apply` respeita",
        ),
        RESISTE: Divida(
            "FATO SUBSTITUÍDO em 16/09/2026, e a atribuição estava ERRADA: esta "
            "linha dizia que «o GE-Proton 11-6 escreve DIRETO no hidraw». Ele "
            "NÃO escreve — medido por `strings` no "
            "`files/lib/wine/x86_64-unix/winebus.so` do 11-6, que só expõe "
            "`hidraw_device_set_output_report` e "
            "`hid_device_set_feature_report`: é um CANO, repassa o report que o "
            "processo Windows manda e não compõe nenhum. O script `proton` "
            "cita hidraw uma vez só, para definir `PROTON_SONY_HIDRAW_XINPUT` "
            "por appid. Quem escreve são DOIS, e cada um tem cobertura "
            "diferente: (a) o SDL do jogo, que tem "
            "`SDL_JOYSTICK_HIDAPI_PS5_PLAYER_LED` no `SDL3.dll` do próprio "
            "Proton — e este caminho o wrapper já fecha, injetando "
            "`SDL_GAMECONTROLLER_IGNORE_DEVICES` para o SDL do jogo não ver o "
            "DualSense real; (b) a Steam Input, pelo "
            "`wow64_ISteamInput_SteamInput007_SetDualSenseTriggerEffect` do "
            "`lsteamclient.so`, que escreve os GATILHOS pelo hidraw do cliente "
            "Steam — e a Steam SEGURA os nós (medido às 15h de 16/09: "
            "hidraw0 e hidraw6). O que sobra de dívida, e é só isto: o veredito "
            "do `escritor_cru` licencia UMA reafirmação no fim da sequência "
            "(GATILHO-DA-COR-01), nunca em regime — repintar durante a partida "
            "faria a barra piscar entre a cor dela e a do jogo. Se a luz e o "
            "gatilho dela sobrevivem a uma PARTIDA inteira com o som do Proton "
            "funcionando é coisa que só ELA pode medir, jogando; a ordem dela "
            "de 16/09 («o som do Proton TEM de funcionar junto com a luz e o "
            "gatilho do perfil») fica aberta até essa medição.",
            desde="2026-09-16",
        ),
        INDEPENDE: Cumprida(
            "core/backend_pydualsense.py::assumir_volume_padrao_na_adocao",
            "SOM-ROTA-02: volume e rota nascem em TODO controle adotado, sem "
            "perfil, sem jogo e sem lançador",
        ),
    },
    "mic": {
        VOLTA: Cumprida(
            "profiles/manager.py::reapply_mic_on_connect",
            "SOM-MIC-REPLUG-01: o `muted` volta pelos DOIS caminhos de replug "
            "do `daemon/connection.py`, e a passagem é assimétrica de propósito "
            "— `True` atravessa (o firmware voltou aberto e o LED vermelho "
            "acende, que é sinal visível), `False` não (já é o default, e "
            "escrevê-lo apagaria o LED). Paga em 16/09/2026, no mesmo dia em "
            "que foi declarada: o preço de errar aqui é de PRIVACIDADE — quem "
            "pediu mudo e recebe aberto fala sem saber que é ouvida.",
        ),
        RESISTE: Divida(
            "o `common[7]` carrega o caminho do microfone e é o mesmo byte da "
            "rota de saída; nada trava um escritor de fora.",
            desde="2026-09-16",
        ),
        INDEPENDE: Cumprida(
            "core/backend_pydualsense.py::set_microphone_mute",
            "fala com o firmware pelo report; não consulta jogo nem lançador",
        ),
    },
    "rumble.policy": {
        VOLTA: Divida(
            "vai injetada no restore de BOOT (`daemon/connection.py`, com a "
            "razão escrita: não tem flag persistido próprio), e o boot NÃO é o "
            "replug. Trocar o cabo no meio da sessão não a devolve.",
            desde="2026-09-16",
        ),
        RESISTE: NaoSeAplica(
            "é política de escala do rumble no nosso lado, não byte do "
            "aparelho: o jogo não tem como escrevê-la."
        ),
        INDEPENDE: Cumprida(
            "daemon/lifecycle.py::apply_profile_rumble_policy",
            "resolve a escala no daemon; nenhum lançador no caminho",
        ),
    },
    "rumble.passthrough": {
        VOLTA: Divida(
            "mesma forma da `rumble.policy`: injetada no restore de boot, "
            "ausente do replug.",
            desde="2026-09-16",
        ),
        RESISTE: NaoSeAplica("idem `rumble.policy`: não é byte do aparelho."),
        INDEPENDE: Cumprida(
            "daemon/lifecycle.py::apply_profile_rumble_passthrough",
            "nenhum lançador no caminho",
        ),
    },
    "controllers": {
        VOLTA: Divida(
            "a metade de ÁUDIO volta desde a SOM-ROTA-03 "
            "(`reapply_speaker_on_connect` lê `controllers[uniq].speaker`), mas "
            "as outras metades do override por peça — gatilho, luz, mic — não "
            "têm gancho de replug próprio: elas dependem do "
            "`_reapply_desired`, que reescreve o DESEJADO corrente e não "
            "reconsulta o perfil.",
            desde="2026-09-16",
        ),
        RESISTE: Cumprida(*_PERFIL_MANDA),
        INDEPENDE: Cumprida(
            "profiles/manager.py::apply_controller_speakers",
            "casa por `uniq` (MAC normalizado), nunca por jogo ou lançador",
        ),
    },
    "mode": {
        VOLTA: NaoSeAplica(
            "o modo (gamepad/nativo/co-op) vive em flag persistido "
            "(`utils/session.py`), não no controle: reconectar não o perde. É "
            "a razão escrita em `daemon/connection.py` para `mode_applier=None` "
            "no restore."
        ),
        RESISTE: NaoSeAplica("não é byte do aparelho."),
        INDEPENDE: Cumprida(
            "daemon/protocols.py::apply_profile_mode", "nenhum lançador no caminho"
        ),
    },
    "mouse": {
        VOLTA: NaoSeAplica(
            "mesma razão do `mode`: flag persistido, e o device virtual de "
            "mouse não morre com o controle."
        ),
        RESISTE: NaoSeAplica("não é byte do aparelho."),
        INDEPENDE: Cumprida(
            "daemon/lifecycle.py::apply_profile_mouse", "nenhum lançador no caminho"
        ),
    },
    "suppress_desktop_emulation": {
        VOLTA: NaoSeAplica("estado do daemon, não do controle."),
        RESISTE: NaoSeAplica("não é byte do aparelho."),
        INDEPENDE: Cumprida(
            "daemon/lifecycle.py::apply_profile_suppression", "nenhum lançador no caminho"
        ),
    },
    "button_actions": {
        VOLTA: NaoSeAplica(
            "vive no device virtual de mouse/teclado, que não morre quando o "
            "DualSense cai — e é recriado pelo liga/desliga da emulação, não "
            "pelo replug."
        ),
        RESISTE: NaoSeAplica("não é byte do aparelho."),
        INDEPENDE: Cumprida(
            "profiles/manager.py::apply_button_actions",
            "resolve pelos dois devices virtuais; nenhum lançador no caminho",
        ),
    },
    "key_bindings": {
        VOLTA: NaoSeAplica("idem `button_actions`: device virtual, não o controle."),
        RESISTE: NaoSeAplica("não é byte do aparelho."),
        INDEPENDE: Cumprida(
            "profiles/manager.py::apply_keyboard", "nenhum lançador no caminho"
        ),
    },
    "remapeamento": {
        VOLTA: NaoSeAplica(
            "é depositado no `store` do gerente e lido por tique pelos dois "
            "`forward_buttons`; o store não morre com o cabo."
        ),
        RESISTE: NaoSeAplica("não é byte do aparelho."),
        INDEPENDE: Cumprida(
            "profiles/manager.py::apply_remapeamento", "nenhum lançador no caminho"
        ),
    },
    # ---------------- o que NÃO chega ao controle ----------------
    "ponte": {
        VOLTA: NaoSeAplica("memória de qual ponte funcionou; nada vai ao controle."),
        RESISTE: NaoSeAplica("nada vai ao controle."),
        INDEPENDE: Divida(
            "é consumida pelo `launch_env`, o caminho de LANÇAMENTO — e o "
            "wrapper que o carrega hoje só é plantado nas Opções de "
            "Inicialização da STEAM. Lutris, Heroic e execução direta não "
            "passam por ele. Ordem dela de 16/09: independe do lançador.",
            desde="2026-09-16",
        ),
    },
    "teclado_emulado": {
        VOLTA: NaoSeAplica(
            "PROVISÓRIO (Z4/T14): a régua existe e nenhum caminho de ativação a "
            "chama — não há fio a reaplicar. Quando o fio subir, as três "
            "respostas mudam junto."
        ),
        RESISTE: NaoSeAplica("o fio não está ligado."),
        INDEPENDE: NaoSeAplica("o fio não está ligado."),
    },
    "name": {p: NaoSeAplica(_NAO_CHEGA) for p in PERNAS},
    "version": {p: NaoSeAplica(_NAO_CHEGA) for p in PERNAS},
    "priority": {p: NaoSeAplica(_NAO_CHEGA) for p in PERNAS},
    "match": {p: NaoSeAplica(_NAO_CHEGA) for p in PERNAS},
}

#: O PISO DA DÍVIDA, medido em 16/09/2026. **Ele só desce.**
#:
#: Nasceu SETE e desceu a SEIS no mesmo dia: o mudo do microfone voltou a
#: sobreviver ao replug (`SOM-MIC-REPLUG-01`), e o teto veio junto — dívida paga
#: que não baixa o teto deixa a próxima entrar de graça, e é o teto que impede
#: esta lista de crescer calada.
#:
#: As SEIS que faltam, cada uma com nome: a defesa do `common[7]` contra
#: escritor de fora, as duas metades do rumble fora do replug, o override por
#: peça que só volta no áudio, o alto-falante contra a escrita crua do Proton, e
#: a ponte que só existe pela Steam.
DIVIDA_MAXIMA = 6


def _dividas() -> list[tuple[str, str, Divida]]:
    return [
        (campo, perna, r)
        for campo, pernas in _PERNAS.items()
        for perna, r in pernas.items()
        if isinstance(r, Divida)
    ]


def _fonte_de(onde: str) -> tuple[Path, str]:
    arquivo, _, simbolo = onde.partition("::")
    return SRC / arquivo, simbolo


# --------------------------------------------------------------------------
# 1. a tabela é exaustiva, e a lista de campos tem UM dono
# --------------------------------------------------------------------------
def test_toda_secao_do_perfil_responde_as_quatro_pernas() -> None:
    """Campo novo no esquema dela não entra sem dizer o que acontece no ciclo.

    É esta linha que impede o quarto caso: quem acrescentar uma seção ao perfil
    tem de responder, por escrito, se ela volta do replug, se resiste ao jogo e
    se depende de lançador.

    MORDIDA: apague uma entrada de `_PERNAS`.
    """
    faltam = sorted(set(_CLASSIFICACAO) - set(_PERNAS))
    sobram = sorted(set(_PERNAS) - set(_CLASSIFICACAO))

    assert not faltam, (
        "campo do perfil sem as quatro pernas declaradas — diga o que acontece "
        "com ele quando o controle reconecta, quando o jogo escreve por cima, e "
        "se ele depende de lançador:\n  " + "\n  ".join(faltam)
    )
    assert not sobram, (
        "perna declarada para campo que não existe mais no esquema:\n  "
        + "\n  ".join(sobram)
    )


def test_cada_campo_responde_as_tres_pernas_desta_regua() -> None:
    """Nenhuma perna fica em branco. Sem resposta é reprovação, não omissão."""
    mudos = [
        f"{campo}.{perna}"
        for campo, pernas in _PERNAS.items()
        for perna in PERNAS
        if perna not in pernas
    ]

    assert not mudos, "perna sem resposta:\n  " + "\n  ".join(sorted(mudos))


# --------------------------------------------------------------------------
# 2. perna CUMPRIDA aponta para símbolo que existe
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("campo", "perna", "onde"),
    [
        (campo, perna, r.onde)
        for campo, pernas in sorted(_PERNAS.items())
        for perna, r in sorted(pernas.items())
        if isinstance(r, Cumprida)
    ],
)
def test_a_perna_cumprida_abre_no_que_promete(campo: str, perna: str, onde: str) -> None:
    """Citação que não abre no símbolo é a armadilha nº 1 desta casa.

    Uma perna "cumprida" apontando para função que alguém renomeou é verde
    sobre nada — exatamente o instrumento falso que este repositório já achou
    seis vezes.

    MORDIDA: troque o símbolo de qualquer `Cumprida` por um nome inventado.
    """
    fonte, simbolo = _fonte_de(onde)

    assert fonte.is_file(), f"{campo}.{perna}: {fonte} não existe"
    corpo = fonte.read_text(encoding="utf-8")
    assert re.search(rf"^\s*(async def|def|class)\s+{re.escape(simbolo)}\b", corpo, re.M), (
        f"{campo}.{perna} promete `{simbolo}` em {fonte.name}, e ele não está lá"
    )


# --------------------------------------------------------------------------
# 3. a dívida é honesta, datada e não cresce
# --------------------------------------------------------------------------
def test_toda_divida_tem_data_e_razao() -> None:
    """Dívida sem data envelhece calada e vira paisagem."""
    torta = [
        f"{campo}.{perna}"
        for campo, perna, d in _dividas()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.desde) or len(d.razao) < 40
    ]

    assert not torta, (
        "dívida sem data ISO ou sem razão que explique o que falta:\n  "
        + "\n  ".join(torta)
    )


def test_a_divida_nao_cresce() -> None:
    """O piso só desce. Uma perna nova faltando é regressão, não status quo.

    MORDIDA: acrescente uma `Divida` a qualquer campo sem baixar o piso.
    """
    dividas = _dividas()

    assert len(dividas) <= DIVIDA_MAXIMA, (
        f"a dívida das quatro pernas subiu para {len(dividas)} (piso: "
        f"{DIVIDA_MAXIMA}). Cure a perna ou explique por que o piso muda:\n  "
        + "\n  ".join(f"{c}.{p}" for c, p, _ in dividas)
    )


# --------------------------------------------------------------------------
# 4. as três curas de 16/09 não voltam atrás
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("campo", "perna"),
    [
        ("triggers", VOLTA),
        ("leds", VOLTA),
        ("speaker", VOLTA),
        ("triggers", RESISTE),
        ("leds", RESISTE),
        ("speaker", INDEPENDE),
    ],
)
def test_o_que_foi_curado_em_16_09_continua_de_pe(campo: str, perna: str) -> None:
    """As três curas daquele dia viram piso: nenhuma delas pode virar dívida.

    `PERFIL-MANDA-01`, `SOM-ROTA-02` e `SOM-ROTA-03` custaram uma sessão inteira
    e uma bancada com a orelha dela. Rebaixá-las a dívida seria desfazê-las sem
    que uma linha vermelha aparecesse.

    MORDIDA: troque qualquer uma destas por `Divida`.
    """
    resposta = _PERNAS[campo][perna]

    assert isinstance(resposta, Cumprida), (
        f"{campo}.{perna} foi CURADA em 16/09/2026 e virou {type(resposta).__name__}"
    )


# --------------------------------------------------------------------------
# 5. a perna 4, medida no código: nada de caminho só-Steam
# --------------------------------------------------------------------------
#: Marcas de um caminho que só funciona pela Steam. Um campo cuja perna de
#: independência aponta para código com uma destas não independe de lançador.
MARCAS_DE_UM_LANCADOR_SO = (
    "STEAM_COMPAT_DATA_PATH",
    "STEAM_COMPAT_CLIENT_INSTALL_PATH",
    "localconfig.vdf",
)


@pytest.mark.parametrize(
    ("campo", "onde"),
    [
        (campo, pernas[INDEPENDE].onde)
        for campo, pernas in sorted(_PERNAS.items())
        if isinstance(pernas[INDEPENDE], Cumprida)
    ],
)
def test_a_independencia_de_lancador_e_medida_no_codigo(campo: str, onde: str) -> None:
    """Declarar "independe" não basta: o código tem de ser lido.

    Ordem dela, 16/09/2026: *"O app deveria construir tudo independente de qual
    jogo ou launcher."* Um campo cuja aplicação passa por
    `STEAM_COMPAT_DATA_PATH` funciona para quem joga pela Steam e falha calado
    para quem usa Lutris, Heroic ou o executável direto.

    MORDIDA: aponte a perna `independe_do_lancador` de qualquer campo para
    `integrations/camadas_vulkan.py`, que hoje depende do prefixo da Steam.
    """
    fonte, simbolo = _fonte_de(onde)
    corpo = fonte.read_text(encoding="utf-8")
    achadas = [m for m in MARCAS_DE_UM_LANCADOR_SO if m in corpo]

    assert not achadas, (
        f"{campo}.independe_do_lancador aponta para {fonte.name}, que menciona "
        f"{achadas} — isso é um caminho de UM lançador só. O símbolo era "
        f"`{simbolo}`."
    )
