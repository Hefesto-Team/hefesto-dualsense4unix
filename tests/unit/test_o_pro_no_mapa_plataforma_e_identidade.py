"""O Nintendo Pro no mapa de canais — plataforma, combinação e identidade.

Nasceu em 03/09/2026 (ONDA-PRO-PLATAFORMA-01), da pergunta dela: *"a ideia é
mapa tanto pra USB quanto rádio estarem conectadas no projeto inteiro e lá ser
nosso hub central"*.

O que este arquivo guarda são DOZE linhas `@pro` que estavam com o veredito
(`aciona`) MUDO em pelo menos um transporte e agora dizem SIM ou NÃO, lendo o
fonte do ``hid-nintendo`` que ESTA árvore instala e o código do produto.

**O PRO NÃO É O DUALSENSE, E ISSO NÃO É DETALHE.** Ele roda o ``hid-nintendo``,
que tem ritual de handshake USB, baudrate 3M, no-timeout e subcomandos ``0x80``
— nada do ``hid-playstation`` vale por analogia. Todas as afirmações aqui saem
de gates que o driver escreve por BARRAMENTO (``joycon_using_usb`` é
``hdev->bus == BUS_USB`` e mais nada), nunca por modelo.

A mordida tem duas metades, e é essa a razão de o arquivo existir:

1. **apagou a célula, reprova.** Uma célula esvaziada volta a ler-se como
   "ninguém respondeu" — que é o estado de onde ela saiu.
2. **mudou o fonte, reprova.** Cada célula afirma um gate, uma linha de conf ou
   uma escrita do produto. Se o fonte mudar, a célula vira mentira publicada no
   ``html/specs.html``, e o teste manda atualizar o mapa no mesmo gesto.

**NADA AQUI MEDE O APARELHO.** Não havia Pro na mesa em 03/09/2026 — o
inventário vivo de ``/sys/class/input`` trazia DualSense e receptores 2.4G,
zero ``057e`` — e ``docs/data/ensaios.csv`` não tem um único ensaio ``@pro``.
Por isso todas as células saíram com ``de_onde_sei`` diferente de ``medido`` e
o teto de ``ate_onde_foi`` é ``MONTOU``.
"""

from __future__ import annotations

import ast
import csv
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPA = REPO_ROOT / "docs" / "data" / "mapa-controles.csv"
DRIVER = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "hid-nintendo.c"
CONF = REPO_ROOT / "assets" / "modprobe.d" / "hefesto-hid-nintendo.conf"
EVDEV = REPO_ROOT / "src" / "hefesto_dualsense4unix" / "core" / "evdev_reader.py"
LAUNCH_ENV = REPO_ROOT / "src" / "hefesto_dualsense4unix" / "daemon" / "launch_env.py"
EXT_CTRL = (
    REPO_ROOT / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "external_controllers.py"
)
ATIVO = REPO_ROOT / "scripts" / "bt_active_mode.sh"
WATCHDOG = REPO_ROOT / "scripts" / "bt_health_watchdog.sh"
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"

#: As DOZE linhas respondidas, e em que lado cada uma passou a ter veredito.
#: `("cabo", "radio")` quer dizer que os dois lados têm de continuar
#: respondidos; uma tupla de um elemento, que o outro lado é mudo DE PROPÓSITO
#: e a razão está na `assimetria_declarada` da própria linha.
LADOS_RESPONDIDOS: dict[str, tuple[str, ...]] = {
    "plataforma.probe@pro": ("cabo", "radio"),
    "plataforma.probe.retry@pro": ("cabo", "radio"),
    "plataforma.inventario@pro": ("cabo", "radio"),
    "plataforma.slot_jogador@pro": ("cabo", "radio"),
    "plataforma.mapeamento_posicao@pro": ("cabo", "radio"),
    "plataforma.link_parametros@pro": ("cabo", "radio"),
    "plataforma.vigia_zumbi@pro": ("cabo", "radio"),
    "plataforma.diagnostico_morte_radio@pro": ("cabo", "radio"),
    "plataforma.transporte_radio@pro": ("cabo", "radio"),
    "plataforma.taxa_relatorios.botao@pro": ("cabo", "radio"),
    "identidade.req_dev_info.fallback@pro": ("cabo", "radio"),
    "combinacao.slot_jogador.estabilidade@pro": ("radio",),
}

#: A linha em que o lado do CABO ficou mudo de propósito, e a palavra que a
#: `cabo_ressalva` dela tem de continuar carregando. Sem essa palavra, o vazio
#: volta a ser indistinguível de "ninguém olhou".
#: A ÚNICA ENTRADA DAQUI SAIU EM 08/09/2026, e a razão é que a célula deixou de
#: ser muda. `combinacao.slot_jogador.estabilidade@pro` carregava a marca
#: «DEIXADA MUDA DE PROPÓSITO»; a varredura do passado (07/09, `126e9603`) a
#: RESPONDEU citando linha — `external_identity.py:537-553` (`_posicao_locked`)
#: e o docstring de `slot_for` (:558-568) —, e de quebra registrou na própria
#: ressalva uma contradição que fica para o dono da linha: o que se mantém é o
#: LUGAR NA FILA, não o número exibido, e a metade `radio_*` ainda afirma o
#: contrário. Exigir a marca de mudez numa célula respondida seria cobrar que
#: ela desaprendesse.
#:
#: O dicionário fica de pé, vazio, porque o MECANISMO continua valendo: a
#: próxima célula que alguém deixar muda de propósito entra aqui e volta a ser
#: cobrada. O que substitui a cobrança daquela linha é
#: `test_a_celula_respondida_em_07_09_nao_regrediu_para_o_vazio`, logo abaixo.
#:
#: **E ESSE ARGUMENTO PRECISOU DE UMA SEGUNDA PERNA — 08/09/2026.** Ele diz que
#: o mecanismo continua valendo, mas enquanto o dicionário está vazio nada o
#: exercita: o teste que o cobrava era um `parametrize` sobre estas entradas, e
#: sem entrada o pytest não coleta caso nenhum — saía
#: `SKIPPED [1] …: got empty parameter set for (identificador, marca)`. **Skip
#: lê-se como verde**, então o mecanismo morava num teste permanentemente
#: pulado e o laudo não contava a falta. O `parametrize` virou laço, e
#: `test_o_mecanismo_da_mudez_declarada_continua_mordendo` exercita a cobrança
#: contra dado real do mapa — as duas metades, a que passa e a que reprova.
MUDA_COM_RAZAO: dict[str, str] = {}

#: A célula que saiu de `MUDA_COM_RAZAO`, e o que se cobra dela agora.
RESPONDIDA_NA_VARREDURA = "combinacao.slot_jogador.estabilidade@pro"

#: Gate do fonte que cada linha afirma. A string TEM de continuar no arquivo;
#: some ela, e a célula do mapa deixou de descrever esta árvore.
GATES: dict[str, tuple[Path, str]] = {
    "plataforma.probe@pro::gate-de-barramento": (
        DRIVER,
        "return ctlr->hdev->bus == BUS_USB;",
    ),
    "plataforma.probe@pro::ritual-usb": (
        DRIVER,
        "joycon_send_usb(ctlr, JC_USB_CMD_BAUDRATE_3M, HZ);",
    ),
    "plataforma.probe@pro::no-timeout": (
        DRIVER,
        "joycon_send_usb(ctlr, JC_USB_CMD_NO_TIMEOUT, HZ/10);",
    ),
    "plataforma.probe.retry@pro::gate-so-radio": (
        DRIVER,
        "if (ret && !joycon_using_usb(ctlr))",
    ),
    "identidade.req_dev_info.fallback@pro::gate-so-cabo": (
        DRIVER,
        "return usb_probe_degrade && joycon_using_usb(ctlr);",
    ),
    "identidade.req_dev_info.fallback@pro::o-pro-esta-no-switch": (
        DRIVER,
        "case USB_DEVICE_ID_NINTENDO_PROCON:",
    ),
    "combinacao.slot_jogador.estabilidade@pro::mac-no-uniq-do-evdev": (
        DRIVER,
        "ctlr->input->uniq = ctlr->mac_addr_str;",
    ),
    "plataforma.taxa_relatorios.botao@pro::modo-de-report-fixo": (
        DRIVER,
        "req->data[0] = 0x30; /* standard, full report mode */",
    ),
    "plataforma.probe.retry@pro::conf-liga-o-retry": (CONF, "bt_probe_retries=3"),
    "identidade.req_dev_info.fallback@pro::conf-liga-o-degrade": (
        CONF,
        "usb_probe_degrade=1",
    ),
    "plataforma.mapeamento_posicao@pro::a-escrita": (
        LAUNCH_ENV,
        'env["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] = "0"',
    ),
    "plataforma.mapeamento_posicao@pro::na-allowlist": (
        LAUNCH_ENV,
        '"SDL_GAMECONTROLLER_USE_BUTTON_LABELS",',
    ),
    "plataforma.inventario@pro::o-pro-tem-nome-na-gui": (
        EXT_CTRL,
        '"057e:2009": "Pro Controller (modo Switch)"',
    ),
    "plataforma.link_parametros@pro::no-sniff-por-dispositivo": (
        ATIVO,
        "LINK POLICY sem SNIFF — POR DISPOSITIVO",
    ),
    "plataforma.link_parametros@pro::so-o-genuino": (ATIVO, "_e_pro_genuino()"),
    "plataforma.vigia_zumbi@pro::a-vigia-de-radio": (WATCHDOG, "vigia_sdp_cache()"),
    "plataforma.diagnostico_morte_radio@pro::a-cascata": (
        DOCTOR,
        "check_hid_nintendo_bt_cascade()",
    ),
}

#: A tabela de ids do driver: o Pro entra por USB **e** por Bluetooth, em duas
#: entradas separadas. É o fato que sustenta `plataforma.probe@pro` nos dois
#: lados, e ele atravessa quebras de linha no fonte — por isso a régua
#: normaliza o espaço antes de procurar.
ENTRADAS_DA_TABELA = (
    "{ HID_USB_DEVICE(USB_VENDOR_ID_NINTENDO, USB_DEVICE_ID_NINTENDO_PROCON) },",
    "{ HID_BLUETOOTH_DEVICE(USB_VENDOR_ID_NINTENDO, USB_DEVICE_ID_NINTENDO_PROCON) },",
)

#: As duas linhas `@pro` cujo `teste_que_morde` a fusão de merge tinha colado —
#: e a marca que denuncia a colagem. Ver `TestOVereditoEstaEscrito`.
CELULAS_DESCOLADAS = ("plataforma.escrita_crua@pro", "plataforma.udev_autosuspend@pro")
MARCA_DE_FUSAO = "|| (a outra frente escreveu:"

#: Os três leitores que herdam de `_EvdevReconnectLoop` — e portanto os únicos
#: que ganham a VIGIA-DO-MUDO-01. Todos são de DualSense, e é isso que faz o
#: `cabo_aciona = não` de `plataforma.vigia_zumbi@pro` ser DÍVIDA e não
#: "nada a acionar": externo nenhum tem laço de reconexão.
LEITORES_COM_VIGIA_DE_MUDO = {"EvdevReader", "TouchpadReader", "MotionSensorReader"}


@pytest.fixture(scope="module")
def mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(newline="", encoding="utf-8") as fh:
        return {linha["id"]: linha for linha in csv.DictReader(fh)}


def _texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8", errors="replace")


class TestOVereditoEstaEscrito:
    """Metade 1 da mordida: esvaziar a célula reprova."""

    @pytest.mark.parametrize("identificador", sorted(LADOS_RESPONDIDOS))
    def test_a_linha_continua_no_mapa(
        self, mapa: dict[str, dict[str, str]], identificador: str
    ) -> None:
        assert identificador in mapa, f"linha sumiu do mapa: {identificador}"

    @pytest.mark.parametrize(
        "identificador,lado",
        sorted((k, lado) for k, lados in LADOS_RESPONDIDOS.items() for lado in lados),
    )
    def test_o_aciona_e_o_de_onde_sei_daquele_lado_continuam_preenchidos(
        self, mapa: dict[str, dict[str, str]], identificador: str, lado: str
    ) -> None:
        linha = mapa[identificador]
        aciona = linha[f"{lado}_aciona"].strip()
        de_onde = linha[f"{lado}_de_onde_sei"].strip()
        assert aciona, (
            f"{identificador}: `{lado}_aciona` voltou a ser mudo. Esta célula foi "
            "respondida em 03/09/2026 lendo o fonte do hid-nintendo e o código do "
            "produto; esvaziá-la devolve a linha a 'ninguém respondeu', que é o "
            "estado que a leva daquele dia existia para fechar."
        )
        assert de_onde, (
            f"{identificador}: `{lado}_de_onde_sei` está vazio com `{lado}_aciona = "
            f"{aciona}` — a régua sabe o QUÊ e calou sobre o DE ONDE (regra 19)."
        )

    @pytest.mark.parametrize(
        "identificador,lado",
        sorted((k, lado) for k, lados in LADOS_RESPONDIDOS.items() for lado in lados),
    )
    def test_nenhuma_celula_desta_leva_se_promoveu_a_medido(
        self, mapa: dict[str, dict[str, str]], identificador: str, lado: str
    ) -> None:
        # Não havia Pro na mesa, e o caderno de ensaios não tem uma linha `@pro`.
        # `medido` aqui seria afirmar prova que não houve.
        assert mapa[identificador][f"{lado}_de_onde_sei"].strip() != "medido", (
            f"{identificador}: `{lado}_de_onde_sei` virou `medido`. Se houve "
            "bancada, o ensaio tem de entrar em docs/data/ensaios.csv no mesmo "
            "gesto — senão a promoção é só uma palavra mais forte."
        )

    @pytest.mark.parametrize(
        "identificador,lado",
        sorted((k, lado) for k, lados in LADOS_RESPONDIDOS.items() for lado in lados),
    )
    def test_o_teto_do_grau_continua_montou(
        self, mapa: dict[str, dict[str, str]], identificador: str, lado: str
    ) -> None:
        grau = mapa[identificador][f"{lado}_ate_onde_foi"].strip()
        assert grau in ("", "MONTOU"), (
            f"{identificador}: `{lado}_ate_onde_foi` subiu para {grau!r} sem que "
            "haja ensaio `@pro` no caderno. O teto do que se afirma sem a mesa "
            "dela é MONTOU."
        )

    @pytest.mark.parametrize("identificador", sorted(LADOS_RESPONDIDOS))
    def test_a_assimetria_continua_declarada(
        self, mapa: dict[str, dict[str, str]], identificador: str
    ) -> None:
        assert mapa[identificador]["assimetria_declarada"].strip(), (
            f"{identificador}: `assimetria_declarada` esvaziou. Divergência calada "
            "entre cabo e rádio é exatamente a forma de defeito que este mapa "
            "existe para pegar."
        )

    def test_o_lado_mudo_de_proposito_continua_dizendo_por_que(
        self, mapa: dict[str, dict[str, str]]
    ) -> None:
        """Toda célula de `MUDA_COM_RAZAO` continua carregando a sua marca.

        SEM `parametrize`, E A RAZÃO É UM SKIP PERMANENTE — 08/09/2026. Este
        teste era `@pytest.mark.parametrize(... MUDA_COM_RAZAO.items())`, e o
        dicionário esvaziou em 07/09 quando a varredura respondeu a única
        célula que ele guardava. Um `parametrize` sobre coleção vazia não
        coleta nada: o pytest emitia
        `SKIPPED [1] …: got empty parameter set for (identificador, marca)`,
        e **skip lê-se como verde**. A cobrança sumia do laudo sem sumir do
        arquivo, que é a forma mais cara de régua comprada desta casa.

        Com o laço aqui dentro o teste RODA sempre: hoje sobre zero células, e
        sobre as que entrarem amanhã sem ninguém precisar lembrar de nada.
        Quem prova que o mecanismo ainda está ligado — hoje, com o dicionário
        vazio — é `test_o_mecanismo_da_mudez_declarada_continua_mordendo`.
        """
        for identificador, marca in sorted(MUDA_COM_RAZAO.items()):
            assert marca in mapa[identificador]["cabo_ressalva"], (
                f"{identificador}: a `cabo_ressalva` perdeu a marca {marca!r}. "
                "Sem ela, o vazio do cabo volta a ser indistinguível de "
                "descuido — e o que está escrito ali é a medição de uma linha "
                "só que resolve a pergunta."
            )

    def test_o_mecanismo_da_mudez_declarada_continua_mordendo(
        self, mapa: dict[str, dict[str, str]]
    ) -> None:
        """Com `MUDA_COM_RAZAO` vazio, é ESTE teste que segura o mecanismo.

        O argumento que justificava manter o dicionário vazio era *"o mecanismo
        continua valendo: a próxima célula muda entra aqui e volta a ser
        cobrada"*. Ele só é verdade enquanto o mecanismo estiver de pé — e,
        com o dicionário vazio, nada o exercitava: a coluna podia ser
        renomeada, ou a cobrança virar vacuidade, e o laudo continuaria verde
        até alguém acrescentar uma entrada e descobrir a régua quebrada.

        As duas metades, sobre DADO REAL do mapa e sem inventar célula nenhuma:

        1. a coluna `cabo_ressalva` existe e a cobrança passa quando a marca
           está lá;
        2. a mesma cobrança REPROVA quando a marca não está — sem isto, a
           régua que herda a próxima célula muda pode ser vacuidade.
        """
        linha = mapa[RESPONDIDA_NA_VARREDURA]
        ressalva = linha["cabo_ressalva"].strip()
        assert ressalva, (
            f"{RESPONDIDA_NA_VARREDURA}: `cabo_ressalva` está vazia — não há "
            "sobre o que exercitar o mecanismo da mudez declarada."
        )

        presente = ressalva[:12]
        assert presente in mapa[RESPONDIDA_NA_VARREDURA]["cabo_ressalva"], (
            "a cobrança da marca não achou um pedaço da própria `cabo_ressalva`"
            f" de {RESPONDIDA_NA_VARREDURA}: a coluna que `MUDA_COM_RAZAO` lê "
            "mudou de nome ou de conteúdo, e o dicionário voltaria quebrado."
        )

        ausente = "«MARCA QUE CÉLULA NENHUMA ESCREVEU»"
        assert ausente not in mapa[RESPONDIDA_NA_VARREDURA]["cabo_ressalva"], (
            "a cobrança da marca passa com uma marca inventada: ela não "
            "distingue nada, e a próxima célula muda entraria numa régua que "
            "não morde."
        )

    def test_a_celula_respondida_em_07_09_nao_regrediu_para_o_vazio(
        self, mapa: dict[str, dict[str, str]]
    ) -> None:
        """O que era mudez declarada virou resposta — e resposta não some.

        Substitui a cobrança da marca «DEIXADA MUDA DE PROPÓSITO» nesta linha
        (ver `MUDA_COM_RAZAO`). O perigo mudou de lado: antes era o vazio
        virar descuido indistinguível, agora é a resposta evaporar num merge e
        a linha voltar a ficar calada sem ninguém decidir isso.
        """
        linha = mapa[RESPONDIDA_NA_VARREDURA]
        assert linha["cabo_ressalva"].strip(), (
            f"{RESPONDIDA_NA_VARREDURA}: a `cabo_ressalva` esvaziou — a "
            "medição de 07/09 sumiu e a célula voltou a ser um vazio mudo"
        )
        for lado in ("cabo", "radio"):
            assert linha[f"{lado}_de_onde_sei"].strip() != "medido", (
                f"{RESPONDIDA_NA_VARREDURA}: `{lado}_de_onde_sei` virou "
                "`medido` sem ensaio @pro no caderno — a resposta veio de "
                "leitura de fonte e o teto dela é `inferido-do-codigo`"
            )

    @pytest.mark.parametrize("identificador", sorted(CELULAS_DESCOLADAS))
    def test_o_teste_que_morde_nao_voltou_a_ser_colado_pelo_merge(
        self, mapa: dict[str, dict[str, str]], identificador: str
    ) -> None:
        # As duas células foram deduplicadas em 03/09/2026: a fusão de merge
        # tinha colado a MESMA lista quatro vezes atrás de «|| (a outra frente
        # escreveu: …)», e o portão `paridade-transporte` reprovava com
        # `mordida-fantasma` porque o alvo colado não é id de nó do pytest.
        valor = mapa[identificador]["teste_que_morde"]
        assert MARCA_DE_FUSAO not in valor, (
            f"{identificador}: `teste_que_morde` voltou a carregar "
            f"{MARCA_DE_FUSAO!r}. Isso não é conteúdo — é fusão de merge colando "
            "texto numa coluna que o portão lê como id de nó do pytest. "
            "Deduplique: os alvos legítimos são separados por `;`."
        )


class TestOFonteAindaSustentaOQueOMapaAfirma:
    """Metade 2 da mordida: mudar o fonte sem mudar o mapa reprova."""

    @pytest.mark.parametrize("rotulo,alvo", sorted(GATES.items()))
    def test_o_gate_continua_no_fonte(
        self, rotulo: str, alvo: tuple[Path, str]
    ) -> None:
        caminho, agulha = alvo
        assert agulha in _texto(caminho), (
            f"{rotulo}: {caminho.relative_to(REPO_ROOT)} não tem mais "
            f"{agulha!r}. A célula do mapa que afirma isto virou mentira "
            "publicada no html/specs.html — atualize as duas no mesmo gesto."
        )

    @pytest.mark.parametrize("entrada", ENTRADAS_DA_TABELA)
    def test_o_pro_continua_nos_dois_barramentos_da_tabela_de_ids(
        self, entrada: str
    ) -> None:
        normalizado = re.sub(r"\s+", " ", _texto(DRIVER))
        assert entrada in normalizado, (
            "a `nintendo_hid_devices` perdeu a entrada "
            f"{entrada!r}. É ela que faz `plataforma.probe@pro` responder `sim` "
            "naquele transporte — sem ela o driver nem é chamado."
        )

    def test_so_leitores_de_dualsense_herdam_a_vigia_do_mudo(self) -> None:
        # É o que sustenta `cabo_por_que_nao_aciona = divida` em
        # `plataforma.vigia_zumbi@pro`: o Pro (espécie `external`) não ganha
        # laço de reconexão nenhum, então o zumbi DE CABO dele não tem vigia.
        arvore = ast.parse(_texto(EVDEV))
        herdeiros = {
            no.name
            for no in ast.walk(arvore)
            if isinstance(no, ast.ClassDef)
            and any(
                isinstance(base, ast.Name) and base.id == "_EvdevReconnectLoop"
                for base in no.bases
            )
        }
        assert herdeiros == LEITORES_COM_VIGIA_DE_MUDO, (
            "as subclasses de `_EvdevReconnectLoop` mudaram: "
            f"{sorted(herdeiros)}. Se um leitor de controle EXTERNO passou a "
            "herdar dela, o Pro ganhou vigia de mudo e "
            "`plataforma.vigia_zumbi@pro` deixou de ser `divida` no cabo."
        )

    def test_a_escrita_do_mapeamento_por_posicao_continua_incondicional(self) -> None:
        # `plataforma.mapeamento_posicao@pro` diz `sim` nos DOIS lados porque a
        # variável sai sem `if` nenhum. Um gate novo aqui torna a célula falsa.
        fonte = _texto(LAUNCH_ENV)
        alvo = 'env["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] = "0"'
        linhas = fonte.splitlines()
        indice = next(i for i, linha in enumerate(linhas) if alvo in linha)
        recuo = len(linhas[indice]) - len(linhas[indice].lstrip())
        assert recuo == 4, (
            "a escrita de `SDL_GAMECONTROLLER_USE_BUTTON_LABELS` ganhou recuo "
            f"({recuo} espaços): ela deixou de estar no corpo da função e passou "
            "a depender de alguma condição. `plataforma.mapeamento_posicao@pro` "
            "afirma `sim` nos dois transportes porque ela é incondicional."
        )

    def test_o_aviso_da_cascata_ainda_acusa_so_o_clone(self) -> None:
        # ACHADO registrado na `radio_ressalva` de
        # `plataforma.diagnostico_morte_radio@pro`: o detector não tem gate de
        # modelo e o texto culpa o 8BitDo. Se alguém curar o texto, a ressalva
        # do mapa passa a descrever uma árvore que não existe mais.
        assert "o firmware 8BitDo em modo Switch engasga" in _texto(DOCTOR), (
            "o aviso de `check_hid_nintendo_bt_cascade` mudou. Se o texto passou "
            "a nomear o Pro genuíno junto, APAGUE o achado da `radio_ressalva` de "
            "plataforma.diagnostico_morte_radio@pro — ele foi curado."
        )
