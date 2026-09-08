"""Elege o microfone do sistema POR CONTROLE — e sabe voltar atrás.

MIC-DA-MESA-ELEICAO-01 (01/09/2026). Decisão dela, com as palavras dela:

    *"Se eu apertar o botão físico mic do controle e ele acender, significa que
    eu quero que o canal de áudio do microfone seja o controle. O botão de
    silenciar é confuso e mexendo com ambos os canais de áudio é péssimo."*

O botão do mic deixa de ser "mudo" e passa a ser **ELEIÇÃO**: apertar quer
dizer *"eu falo por este controle"*, e o canal de captura DAQUELE controle vira
o microfone que o sistema usa.

O QUE ESTE MÓDULO NÃO FAZ, e cada linha é uma medição:

* **Não escreve no `common[9]`.** O mudo do firmware continua sendo do
  `hid-playstation`, que alterna `ds->mic_muted` na borda do botão. Tomar
  aquela posse APAGARIA o sujeito do gesto — sem a borda do kernel não existe
  "quem apertou". As três recusas (BT-E-VPAD-01, MIC-BT-DONO-01,
  MIC-DOIS-DONOS-01) continuam inteiras, e agora também por impossibilidade
  construtiva.
* **Não toca em drop-in, não chama `doctor --fix-mic`, não reinicia o
  WirePlumber.** Isso é `--promote-source`, que é um gesto HUMANO explícito e
  muda a política da máquina inteira. Um toque de botão não pode fazer isso a
  cada vez, com ela usando o computador.
* **Não inventa critério de "fonte que se sustenta".** O dono é
  `scripts/fix_wireplumber_default_source.sh` (que por sua vez chama o
  `doctor.sh:_sources_com_porta_usavel`). Do lado Python não existe UMA linha
  que olhe porta de captura, e escrever uma criaria a segunda régua sobre o
  mesmo estado — o defeito RECEITA-ERRADA-01, que esta casa já pagou duas vezes
  exatamente aqui.

A ARMADILHA QUE ESTE MÓDULO EXISTE PARA NÃO CAIR, medida em três lugares
independentes: **o WirePlumber não honra nó eleito que não se sustenta.** Ele
reelege sozinho, e a preferência que você acabou de gravar vira lixo. Por isso
a pós-condição canônica é o ATIVO relido, nunca o `configured` — e por isso
declarar sucesso pela escrita é o *"silêncio não é sucesso"* na forma mais cara
que ele tem aqui: o LED do controle passaria a mentir sobre o microfone dela.

E **guardar o anterior é obrigatório**, porque eleger PERSISTE: o valor de
antes é empurrado pilha abaixo, e numa mesa em turnos quatro eleições empurram
o microfone real dela quatro degraus para baixo, caladas.

A ELEIÇÃO ENCOLHEU — CANAL-POR-CONTROLE-01, 03/09/2026
-------------------------------------------------------
Decisão dela, com as palavras dela e sem corrigi-las:
*"4 controles os 4 tem que ter canais de entrada unico pra cada qual."*  (noqa-acento)

Duas coisas que este módulo tratava como uma passam a ser duas:

* **TER CANAL** não é escasso. Cada DualSense pode publicar o canal de captura
  DELE, e ninguém precisa tirá-lo de ninguém;
* **SER O PADRÃO DO SISTEMA** é o único recurso genuinamente único, porque
  `pactl get-default-source` devolve UM nome. **É só isto que a eleição
  decide**, e é o que ela sempre fez de fato.

O que muda no código: quando o canal do controle não está no ar, este módulo
para de recusar de saída e **PEDE o canal** pelo gancho
:func:`registrar_pedidor_de_canal`, espera o PipeWire publicá-lo, e então
elege. O gancho existe para que o sentido do import continue certo — quem o
instala é `daemon/subsystems/bt_mic.py`, que é o dono da ponte; este módulo só
conhece um chamável.

**Nenhuma frase nova.** As recusas continuam sendo as que já existiam, palavra
por palavra: quando o pedido não é atendido no orçamento, a resposta é a mesma
de antes. Ela recusou a PREMISSA de um recado de tela sobre "perder o
microfone", e nenhuma foi escrita.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    CasamentoUSB,
    escolher_fonte,
    fontes_dualsense,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_TIMEOUT_S = 3.0

#: Quanto esperar o grafo assentar depois de escrever, antes de RELER o ativo.
#: Mesmo orçamento do `verify_active_not_dualsense` do shell (~5 s em passos de
#: 250 ms) e pela mesma razão medida: o WirePlumber leva alguns segundos para
#: reeleger, e ler antes disso dá veredicto que depende do relógio
#: (O-VEREDICTO-QUE-DEPENDIA-DO-RELOGIO-01).
SETTLE_PASSOS = 20
SETTLE_PASSO_S = 0.25

#: O nó de ESCASSEZ do PipeWire: o que ele publica quando NADA está pronto.
#: Não é microfone e não é monitor — é "ainda não sei", e por isso não conta
#: como resposta. Mesmo critério de `e_o_nada_do_pipewire` no shell.
_NADA_DO_PIPEWIRE = "auto_null"

#: Quanto esperar o canal PEDIDO aparecer no PipeWire. A ponte tem de abrir o
#: hidraw, carregar o `module-pipe-source` e o servidor tem de publicar o nó —
#: três passos que não são instantâneos e também não levam segundos. Orçamento
#: menor que o do assentamento (`SETTLE_*`) de propósito: aqui a espera é ANTES
#: da escrita, e somar os dois num toque de botão é o que a pessoa sente.
ESPERA_DO_CANAL_PASSOS = 12
ESPERA_DO_CANAL_PASSO_S = 0.25

#: Quem sabe SUBIR o canal de captura de um controle. `None` = ninguém está
#: atendendo (subsystem no chão, ou processo que não é o daemon), e aí pedir é
#: um `False` honesto em vez de uma espera que não vai dar em nada.
_PEDIDOR_DE_CANAL: Callable[[str], bool] | None = None


def registrar_pedidor_de_canal(
    pedidor: Callable[[str], bool] | None,
) -> Callable[[str], bool] | None:
    """Instala quem atende pedido de canal. Devolve o anterior, para restaurar.

    Quem chama é `daemon/subsystems/bt_mic.BtMicSubsystem.start`, e o sentido
    importa: **daemon importando `integrations`**. Se este módulo importasse o
    subsystem, uma integração passaria a depender do daemon — a camada errada,
    e um ciclo esperando acontecer.
    """
    global _PEDIDOR_DE_CANAL
    anterior = _PEDIDOR_DE_CANAL
    _PEDIDOR_DE_CANAL = pedidor
    return anterior


def pedir_canal(uniq: str) -> bool:
    """Pede o canal de captura do controle `uniq`. False = ninguém atendeu.

    Nunca levanta: um pedidor que exploda vale como *"não atendeu"*, e o
    caminho segue para a recusa de sempre. O lado inseguro seria o contrário —
    o toque no botão do microfone dela virando um traceback no laço do daemon.
    """
    pedidor = _PEDIDOR_DE_CANAL
    if pedidor is None:
        return False
    try:
        return bool(pedidor(uniq))
    except Exception:  # best-effort: o gesto dela não vira traceback
        logger.debug("eleicao_mic_pedido_de_canal_falhou", exc_info=True)
        return False


#: Quem ouve a PALAVRA DELA sobre o microfone de um controle. `None` = ninguém
#: está atendendo (subsystem no chão, ou processo que não é o daemon). Mesmo
#: molde e mesmo sentido de import de `_PEDIDOR_DE_CANAL`, logo acima.
_DIZEDOR_DO_NO_AR: Callable[[str, bool], bool] | None = None

#: Quem esquece a palavra dela (a decisão volta ao ouvinte da source).
_ESQUECEDOR_DA_PALAVRA: Callable[[str], bool] | None = None


def registrar_dizedor_do_no_ar(
    dizedor: Callable[[str, bool], bool] | None,
    esquecedor: Callable[[str], bool] | None = None,
) -> tuple[Callable[[str, bool], bool] | None, Callable[[str], bool] | None]:
    """Instala quem atende a palavra dela. Devolve os anteriores, para restaurar.

    Quem chama é `daemon/subsystems/bt_mic.BtMicSubsystem.start`, pela mesma
    razão que `registrar_pedidor_de_canal`: **daemon importando
    `integrations`**, nunca o contrário.
    """
    global _DIZEDOR_DO_NO_AR, _ESQUECEDOR_DA_PALAVRA
    anteriores = (_DIZEDOR_DO_NO_AR, _ESQUECEDOR_DA_PALAVRA)
    _DIZEDOR_DO_NO_AR = dizedor
    _ESQUECEDOR_DA_PALAVRA = esquecedor
    return anteriores


def dizer_no_ar(uniq: str, ligado: bool) -> bool:
    """*"Quero/não quero este microfone no ar"*. False = ninguém atendeu.

    **É O SEGUNDO DONO DO 0x32 do rádio**, e ele faltava. O ato do microfone
    já fazia as duas metades que tinha — o canal no sistema e o bit do
    firmware —, e nenhuma delas alcança o `0x32` que põe o microfone do
    controle no ar por Bluetooth: esse seguia só o ouvinte da source, e eleger
    o canal como fonte padrão deixa a source ``SUSPENDED``. O resultado medido
    no journal dela em 07/09/2026 foi um ato respondendo `feito=True` sobre um
    microfone mudo no ar.

    **NO CABO ISTO NÃO FAZ NADA, e é o desfecho certo:** não há ponte, não há
    `0x32`, e a placa USB já publica o canal sozinha — quem atende só conhece
    nós de Bluetooth. Chamar daqui para os dois transportes é o que mantém uma
    regra só no ato, em vez de um `if` de transporte no caminho dela.

    Nunca levanta, pela mesma razão de `pedir_canal`: o toque no botão do
    microfone dela não vira traceback no laço do daemon.
    """
    dizedor = _DIZEDOR_DO_NO_AR
    if dizedor is None:
        return False
    try:
        return bool(dizedor(uniq, ligado))
    except Exception:  # best-effort: o gesto dela não vira traceback
        logger.debug("eleicao_mic_palavra_dela_falhou", exc_info=True)
        return False


def esquecer_a_palavra(uniq: str) -> bool:
    """Ela deixa de ter dito qualquer coisa sobre este microfone.

    Não é o mesmo que `dizer_no_ar(uniq, False)`: `False` é *"me cale"* e vence
    um aplicativo gravando; esquecer devolve a decisão ao ouvinte da source.
    Quem chama é a perda da eleição — ver
    `daemon/subsystems/hotkey._apagar_a_luz_de_quem_perdeu_o_canal`.
    """
    esquecedor = _ESQUECEDOR_DA_PALAVRA
    if esquecedor is None:
        return False
    try:
        return bool(esquecedor(uniq))
    except Exception:  # best-effort: o gesto dela não vira traceback
        logger.debug("eleicao_mic_esquecer_a_palavra_falhou", exc_info=True)
        return False


def _ambiente_c() -> dict[str, str]:
    """`LC_ALL=C`: a saída do `pactl` é TRADUZIDA nesta máquina."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def _rodar(argv: list[str]) -> tuple[int, str]:
    """Roda e devolve `(rc, stdout)`. Nunca levanta — ausência é resposta."""
    exe = shutil.which(argv[0])
    if exe is None:
        return (127, "")
    try:
        proc = subprocess.run(  # argv fixo, sem shell
            [exe, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            env=_ambiente_c(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return (127, "")
    return (proc.returncode, proc.stdout.strip())


def _script_do_wireplumber() -> Path | None:
    """O script que é DONO do critério de fonte que se sustenta.

    Procurado ao lado do pacote (árvore de desenvolvimento) e no `PATH`
    (instalado). `None` = não dá para consultar, e nesse caso a eleição RECUSA
    em vez de inventar um critério próprio.
    """
    nome = "fix_wireplumber_default_source.sh"
    aqui = Path(__file__).resolve()
    for pai in aqui.parents:
        candidato = pai / "scripts" / nome
        if candidato.is_file():
            return candidato
    achado = shutil.which(nome)
    return Path(achado) if achado else None


def _script_conhece(script: Path, flag: str) -> bool:
    """O script instalado ACEITA esta flag? Se não, não se chama.

    ISTO NÃO É PARANOIA — foi MEDIDO em 01/09/2026, arrancando a flag do shell
    para ver a régua reprovar. O `for arg in "$@"` daquele script termina em
    ``*) printf 'aviso: argumento desconhecido'``, e o `MODE` **continua sendo
    o default, que é `install`**. Ou seja: chamar o script com uma flag que ele
    não conhece não devolve erro — ele RODA O INSTALADOR, escreve drop-in e
    reinicia o WirePlumber da sessão dela.

    O caso real disso não é hipótese: o produto instalado em `~/.local/bin`
    pode ser mais VELHO que este pacote (é um arquivo por máquina, um só para
    as duas árvores). Uma eleição de microfone jamais pode virar uma
    instalação silenciosa porque o script do disco é de ontem.

    Ler o arquivo é barato e é a única pergunta honesta: *"você conhece esta
    palavra?"*. `False` faz a eleição RECUSAR, que é o desfecho certo.
    """
    try:
        texto = script.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return flag in texto


def fonte_se_sustenta(nome: str) -> bool | None:
    """A fonte `nome` para de pé? `None` = não deu para consultar.

    Três respostas, e as três são diferentes: `True` (se sustenta), `False`
    (consultei e não se sustenta), `None` (não consegui consultar — sem script,
    sem `pactl`). Transformar `None` em `False` faria a eleição recusar por
    falta de instrumento e culpar o nó.
    """
    script = _script_do_wireplumber()
    if script is None or not _script_conhece(script, "--fonte-se-sustenta"):
        return None
    rc, saida = _rodar(["bash", str(script), "--fonte-se-sustenta", nome])
    if rc != 0:
        return None
    return saida.strip() == nome


def melhor_fonte_elegivel() -> str | None:
    """A melhor fonte de captura que NÃO é o controle, ou `None`.

    `None` aqui quer dizer *"não há para onde voltar"* — e isso é uma resposta,
    não uma falha: medido nesta bancada em 01/09/2026, com a webcam
    desconectada e as três portas analógicas da placa-mãe `not available`, o
    dono do critério devolve VAZIO. O certo nesse caso é **não eleger nada** e
    dizer isso na tela; cair no `.monitor` do sink é o defeito
    MONITOR-QUE-VENCE-01 inteiro (gravar o áudio de SAÍDA em vez da voz dela).
    """
    script = _script_do_wireplumber()
    if script is None or not _script_conhece(script, "--melhor-fonte-elegivel"):
        return None
    rc, saida = _rodar(["bash", str(script), "--melhor-fonte-elegivel"])
    if rc != 0:
        return None
    nome = saida.strip().splitlines()[-1].strip() if saida.strip() else ""
    return nome or None


def fonte_ativa() -> str | None:
    """`pactl get-default-source`, ou `None` quando a resposta não significa nada.

    As TRÊS não-respostas, e é obrigatório tratá-las: vazio, `auto_null*` (o nó
    de escassez do PipeWire) e qualquer `.monitor` (o loopback da saída). Um
    `.monitor` como "microfone padrão" é o defeito de gravar o som que sai em
    vez da voz — e o medidor de nível mostra sinal, então PARECE funcionar.
    """
    rc, saida = _rodar(["pactl", "get-default-source"])
    if rc != 0:
        return None
    nome = saida.strip()
    if not nome:
        return None
    baixa = nome.lower()
    if baixa.startswith(_NADA_DO_PIPEWIRE) or baixa.endswith(".monitor"):
        return None
    return nome


@dataclass
class ResultadoDaEleicao:
    """O que a eleição conseguiu, e nunca o que ela mandou.

    `ok` só é `True` quando o ATIVO RELIDO é o alvo. `motivo` diz por que não,
    e é o texto que vai para a tela — a régua desta casa é que ausência de
    resposta vira frase, nunca silêncio com cara de sucesso.
    """

    ok: bool
    alvo: str | None = None
    ativo: str | None = None
    motivo: str = ""


@dataclass
class EleitorDeMicrofone:
    """Elege por `uniq`, confere relendo o ativo, e sabe o caminho de volta.

    Um por sessão do daemon: ele guarda a fonte padrão que existia ANTES da
    primeira eleição, e é essa memória que o caminho de volta consulta.
    """

    #: A fonte padrão de ANTES da primeira eleição desta sessão. `None` = ainda
    #: não elegemos nada (ou não deu para ler). É gravada UMA vez, de propósito:
    #: gravar de novo a cada eleição faria a segunda eleição "lembrar" da
    #: primeira, e numa mesa em turnos a memória viraria o controle anterior.
    anterior: str | None = None
    _guardou: bool = field(default=False, repr=False)

    #: O `uniq` do controle que está com o microfone da mesa AGORA. `None` =
    #: ninguém elegeu (ou já devolveu, e a devolução foi CONFERIDA).
    #:
    #: **Ele só muda com a releitura do ATIVO, nos dois sentidos.** Eleição que
    #: o WirePlumber desfaz não anota dono; devolução que não conseguiu
    #: devolver não tira o dono, porque o padrão do sistema continua sendo o
    #: canal dele. É o mesmo *"a pós-condição canônica é o ATIVO relido"* do
    #: topo do módulo, aplicado à posse.
    #:
    #: ACHADO DA AUDITORIA DE 02/09/2026, e é sobre a mesa de quatro que ela
    #: nomeou (*"com 4 pessoas com controle na mão localmente isso é
    #: necessário"*). Sem este campo, `_eleger_ou_devolver` decidia só pelo bit
    #: `mudo` e nunca perguntava se ESTE `uniq` era o eleito: a J1 elegia, o J2
    #: apertava o botão DELE, e o `devolver_o_microfone()` tirava o padrão do
    #: sistema da J1 — que continuava com o LED aceso dizendo "estou no ar".
    #: É exatamente a mentira que esta onda existe para matar.
    eleito: str | None = None

    #: O NOME DO CANAL do controle eleito, CONFERIDO — o `alvo` que a releitura
    #: do ativo confirmou no momento da eleição. `None` = ninguém elegeu, ou a
    #: posse veio de fora (teste antigo que crava `eleito` na mão).
    #:
    #: Ele existe para responder UMA pergunta que `eleito` sozinho não responde:
    #: *"o microfone deste controle ainda é o padrão do sistema?"*. Sem o nome,
    #: a releitura do ativo devolve uma string que não dá para comparar com
    #: nada, e os TRÊS desfechos de recusa de `_eleger_nome` viram um só.
    #:
    #: ACHADO DA AUDITORIA DE 02/09/2026, e é o `eleicao_mic_nao_pegou` — o
    #: defeito que este módulo inteiro existe para pegar — reintroduzido no
    #: caminho de VOLTA. Medido com o eleitor de verdade e o `pactl` dublado:
    #: a J1 elege, aperta o botão de novo, o `set-default-source` é ACEITO
    #: (`rc == 0`) e o ativo relido é um TERCEIRO. O canal deixou de ser dela,
    #: e o `state_full` publicava `eleito: …011` com `ativo: mic_de_um_terceiro`
    #: e o plástico ACESO. Com o nome guardado, `_o_eleito_saiu_do_ar` separa
    #: esse desfecho do caso em que o WirePlumber devolveu o canal ao PRÓPRIO
    #: controle — em que a luz tem de continuar acesa.
    fonte_do_eleito: str | None = None

    def guardar_anterior(self) -> str | None:
        """Guarda o `get-default-source` de antes — UMA vez por sessão."""
        if self._guardou:
            return self.anterior
        self._guardou = True
        self.anterior = fonte_ativa()
        logger.info("eleicao_mic_guardou_anterior", anterior=self.anterior)
        return self.anterior

    # -- eleger -----------------------------------------------------------

    def eleger_por_uniq(
        self,
        uniq: str,
        *,
        fontes: list[str],
        uniqs_com_audio: list[str],
        usb: CasamentoUSB | None = None,
    ) -> ResultadoDaEleicao:
        """Elege o canal de captura do controle `uniq` como padrão do sistema.

        A ordem é a ordem, e cada passo já falhou de um jeito diferente:

        1. resolve `uniq → nome` pelo dono da resolução (`escolher_fonte`);
        2. GUARDA o anterior (só na primeira vez da sessão, em `_eleger_nome`);
        3. pergunta ao dono do critério se o alvo SE SUSTENTA — **antes** de
           escrever, porque eleger um nó que não para de pé sobrescreve a
           preferência dela por lixo que o WirePlumber desfaz sozinho;
        4. escreve com `pactl set-default-source`;
        5. ESPERA o grafo assentar e **relê o ATIVO**;
        6. só devolve `ok=True` se o ativo relido for o alvo;
        7. e o passo que faltava: **a eleição que FRACASSA também é uma
           medição do ativo**, e ela pode provar que o canal de quem estava
           com o microfone deixou de ser o padrão. Aí a posse DELE cai.

        **O PASSO 7 É O ACHADO DA AUDITORIA DE 02/09/2026**, e ele é o mesmo
        `eleicao_mic_nao_pegou` que este módulo existe para pegar, deixado de
        fora do caminho de IDA. O caminho de VOLTA já o tratava
        (`_o_eleito_saiu_do_ar`); a ida só sabia dizer "não foi você" e nunca
        perguntava se ainda era do outro. Reproduzido com o eleitor de verdade
        e o `pactl` dublado:

            J1 elege  → eleito=…011, fonte_do_eleito=bluez_input.…_11, ativo=…_11
            J2 aperta → set-default-source …_22 ACEITO (rc=0), ativo relido =
                        alsa_input.pci-0000_00_1f.3.analog-stereo (um TERCEIRO)
            depois    → eleito=…011 e o ativo do sistema NÃO é mais o canal dela

        O `state_full` publicava `eleito: …011` com o canal em um terceiro, e o
        plástico da J1 seguia ACESO afirmando *"estou no ar"*. A escrita passou
        — o padrão do sistema saiu do canal dela — e ninguém tinha o que ela
        perdeu. É a mentira de segunda geração no caminho de IDA, com o
        agravante de que a J1 não tocou em nada.
        """
        alvo = escolher_fonte(fontes, uniq, uniqs_com_audio, usb)
        if alvo is None:
            return ResultadoDaEleicao(
                ok=False,
                motivo=(
                    "não há canal de captura atribuível a este controle — no "
                    "rádio ele só aparece com a ponte de microfone de pé"
                ),
            )
        resultado = self._eleger_nome(alvo)
        # QUEM ESTÁ COM O MICROFONE só muda quando a eleição foi CONFERIDA —
        # `_eleger_nome` releu o ativo e ele bate com o alvo. Marcar na escrita
        # seria a mesma mentira de segunda geração que o LED evita: registrar
        # como dono quem o WirePlumber já reelegeu por cima.
        if resultado.ok:
            self.eleito = uniq
            self.fonte_do_eleito = alvo
        elif self._o_eleito_saiu_do_ar(resultado):
            # E A ELEIÇÃO QUE FALHOU AINDA MEDIU O ATIVO. Os três desfechos de
            # recusa de `_eleger_nome` NÃO são iguais aqui, exatamente como não
            # são no caminho de volta: dois não escreveram nada (a fonte não se
            # sustenta, o `pactl` recusou) e deixam o canal onde estava; o
            # TERCEIRO escreveu, o WirePlumber reelegeu por cima, e o ativo
            # relido não é o canal de NINGUÉM que a gente conheça — nem do alvo
            # nem do eleito. Quem separa os três é `_o_eleito_saiu_do_ar`, que
            # compara o ativo relido com o NOME do canal do eleito.
            #
            # Soltar a posse aqui não é "declarar fracasso": é a mesma régua do
            # módulo inteiro — a pós-condição canônica é o ATIVO RELIDO — lida
            # sobre quem ela de fato descreve. Manter a posse seria o produto
            # afirmando que o microfone da J1 está no ar depois de ele mesmo ter
            # tirado o canal dela, num gesto que ela não fez.
            logger.warning(
                "eleicao_mic_tirou_o_canal_de_quem_o_tinha",
                ex_dono=self.eleito,
                fonte_do_ex_dono=self.fonte_do_eleito,
                ativo=resultado.ativo,
                alvo=resultado.alvo,
            )
            self.eleito = None
            self.fonte_do_eleito = None
        return resultado

    def _o_eleito_saiu_do_ar(self, resultado: ResultadoDaEleicao) -> bool:
        """A releitura do ATIVO prova que o canal do eleito deixou de ser o padrão?

        É a MESMA régua do resto do módulo — a pós-condição canônica é o ATIVO
        RELIDO (ADR-019) — aplicada à posse. `_eleger_nome` tem QUATRO
        desfechos e três devolvem ``ok=False``; tratá-los como um é o que
        deixava a luz acesa sobre um canal que a própria medição dizia não ser
        mais dele.

        **VALE NOS DOIS CAMINHOS, e a segunda metade é de 02/09/2026.** Ela
        nasceu na VOLTA (`devolver_o_microfone`) e faltava na IDA
        (`eleger_por_uniq`) — onde o desfecho é o mesmo e o sujeito é outro:
        quem perde o canal não é quem apertou o botão, é o dono anterior. A
        pergunta que esta função responde não depende de qual gesto a
        provocou; ela é sempre *"o ativo relido ainda é o canal do eleito?"*.

        ==================================  ====================  ============
        desfecho de `_eleger_nome`          o que o ativo diz      saiu do ar?
        ==================================  ====================  ============
        ``ok=True``                         é o destino da volta   **sim**
        a fonte não se sustenta             nada foi escrito       não
        o `pactl` recusou (``rc != 0``)     a escrita não pegou    não
        escreveu e o ativo é o canal DELE   o WirePlumber voltou   não
        escreveu e o ativo é um TERCEIRO    o canal não é dele     **sim**
        escreveu e o ativo é ilegível       não deu para ler       não
        ==================================  ====================  ============

        **"NÃO SEI" NUNCA VIRA "SAIU"**, e é a mesma regra que
        `daemon/subsystems/recado_do_microfone.mesa_de_agora` aplica ao `None`
        do backend: ativo ilegível, ou posse que veio de fora sem o nome do
        canal, deixam o dono de pé. Soltar a posse ali seria declarar que o
        microfone saiu do ar por não termos conseguido perguntar — o
        *"silêncio não é sucesso"* com o sinal trocado.
        """
        if resultado.ok:
            return True
        if resultado.ativo is None or self.fonte_do_eleito is None:
            return False
        return resultado.ativo != self.fonte_do_eleito

    def _eleger_nome(self, alvo: str) -> ResultadoDaEleicao:
        # A memória é guardada AQUI, e não só em `eleger_por_uniq`: toda
        # escrita passa por este método (o caminho de volta também), e uma
        # única porta sem a guarda deixaria a preferência dela cair pilha
        # abaixo sem que nada tivesse anotado o que era antes.
        self.guardar_anterior()
        sustenta = fonte_se_sustenta(alvo)
        if sustenta is None:
            return ResultadoDaEleicao(
                ok=False,
                alvo=alvo,
                motivo=(
                    "não deu para consultar quais fontes se sustentam — recuso "
                    "eleger às cegas em vez de inventar um segundo critério"
                ),
            )
        if not sustenta:
            return ResultadoDaEleicao(
                ok=False,
                alvo=alvo,
                motivo=(
                    f"{alvo} não tem porta de captura usável — eleger aqui é o "
                    "que o WirePlumber desfaz sozinho, sobrescrevendo a "
                    "preferência anterior"
                ),
            )
        rc, _ = _rodar(["pactl", "set-default-source", alvo])
        if rc != 0:
            return ResultadoDaEleicao(
                ok=False, alvo=alvo, motivo=f"'pactl set-default-source {alvo}' falhou"
            )
        ativo = self._assentar_e_reler(alvo)
        if ativo == alvo:
            logger.info("eleicao_mic_ok", alvo=alvo, anterior=self.anterior)
            return ResultadoDaEleicao(ok=True, alvo=alvo, ativo=alvo)
        logger.warning("eleicao_mic_nao_pegou", alvo=alvo, ativo=ativo)
        return ResultadoDaEleicao(
            ok=False,
            alvo=alvo,
            ativo=ativo,
            motivo=(
                "a escrita foi aceita mas o microfone ATIVO continua "
                f"{ativo or '<nenhum>'} — o WirePlumber reelegeu por cima"
            ),
        )

    def _assentar_e_reler(self, alvo: str) -> str | None:
        """Espera o grafo assentar e relê o ATIVO — nunca o `configured`.

        A pós-condição canônica desta casa é o ATIVO (ADR-019). O
        `default.configured.audio.source` é o que PEDIMOS; o ativo é o que o
        WirePlumber de fato está usando, e a diferença entre os dois é
        exatamente o defeito que este módulo existe para pegar.
        """
        ativo: str | None = None
        for _ in range(SETTLE_PASSOS):
            ativo = fonte_ativa()
            if ativo == alvo:
                return ativo
            time.sleep(SETTLE_PASSO_S)
        return ativo

    def eleger_o_controle(
        self, uniq: str, uniqs_conectados: list[str]
    ) -> ResultadoDaEleicao:
        """`eleger_por_uniq` juntando os dados do PipeWire e do sysfs sozinho.

        É esta a porta que o daemon usa: o subsistema das bordas entrega um
        `uniq` e mais nada, e quem monta o casamento por dispositivo USB é
        aqui — do lado do daemon, e não do lado da janela, porque foi
        exatamente essa a razão de `escolher_fonte` ter mudado de camada.

        **E é aqui que o canal PASSOU A SER PEDIDO** (CANAL-POR-CONTROLE-01):
        o controle no rádio não publica fonte nenhuma até a ponte subir, e até
        03/09/2026 este método recusava por causa disso — a pessoa apertava o
        botão e o produto respondia que não havia canal, sem nada que ela
        pudesse fazer a respeito de dentro do produto.
        """
        fontes, usb = self._canal_no_ar(uniq, list(uniqs_conectados))
        if not fontes:
            return ResultadoDaEleicao(
                ok=False,
                motivo=(
                    "o PipeWire não publica canal de captura nenhum para o "
                    "controle — no rádio isso precisa da ponte de microfone"
                ),
            )
        return self.eleger_por_uniq(
            uniq,
            fontes=fontes,
            uniqs_com_audio=list(uniqs_conectados),
            usb=usb,
        )

    def _canal_no_ar(
        self, uniq: str, conectados: list[str]
    ) -> tuple[list[str], CasamentoUSB | None]:
        """As fontes de agora, PEDINDO o canal deste controle se ele faltar.

        A pergunta é feita pelo dono dela — `escolher_fonte` —, e não por uma
        segunda régua escrita aqui: já existe canal atribuível a este controle?
        Se existe (o caso do CABO, que publica sozinho), nada é pedido e nada é
        esperado; o toque no botão custa o mesmo de sempre.

        Se não existe, pede uma vez e espera o PipeWire publicar. A espera olha
        só as regras que não dependem do casamento USB (`uniqs_com_audio` vazio
        e `usb=None`), porque o que vai nascer é a source da ponte de BT, cujo
        nome carrega o rabo do MAC — e assim cada volta custa UM `pactl list
        sources short`, e não o `pactl list sources` inteiro mais o sysfs.

        **Nenhuma frase nova sai daqui.** Quando o pedido não é atendido no
        orçamento, devolve-se o que o PipeWire tem, e quem escreve a recusa é o
        caminho de sempre — com o texto de sempre.
        """
        fontes = fontes_de_captura_agora()
        usb = casamento_usb_agora(conectados) if fontes else None
        if escolher_fonte(fontes, uniq, conectados, usb) is not None:
            return fontes, usb
        if not pedir_canal(uniq):
            return fontes, usb
        for _ in range(ESPERA_DO_CANAL_PASSOS):
            time.sleep(ESPERA_DO_CANAL_PASSO_S)
            novas = fontes_de_captura_agora()
            if escolher_fonte(novas, uniq, [], None) is not None:
                logger.info("eleicao_mic_canal_no_ar", uniq=uniq)
                return novas, casamento_usb_agora(conectados)
        logger.warning("eleicao_mic_canal_nao_subiu", uniq=uniq)
        return fontes, usb

    # -- o caminho de volta (item 6 dela) ---------------------------------

    def devolver_o_microfone(self) -> ResultadoDaEleicao:
        """O controle eleito saiu do ar: elege a melhor fonte que NÃO é ele.

        **QUEM CHAMA, MEDIDO (02/09/2026):** um só — o ramo do botão do
        microfone em `daemon/subsystems/hotkey._eleger_ou_devolver`, quando o
        ELEITO vai a mudo. Este docstring dizia *"quando o controle eleito
        passa a MUDO, cai do rádio/cabo, ou a ponte de microfone dele cai"*, e
        as duas últimas eram falsas: `grep -rn "devolver_o_microfone" src/`
        devolve esta definição e aquela única chamada, e as TRÊS escritas de
        `self.eleito` neste módulo saem da MESMA releitura do ATIVO — duas em
        `eleger_por_uniq` (anota o dono quando o ativo relido é o canal dele;
        SOLTA o dono anterior quando o ativo relido prova que o canal deixou de
        ser dele) e uma neste método, pela mesma prova. As três passam por
        `_o_eleito_saiu_do_ar` ou pelo `ok` que ele já cobre. (Eram duas até a
        segunda auditoria de 02/09, que achou o caminho de IDA sem a pergunta;
        e antes disso a condição daqui era `resultado.ok`, que confundia os
        três desfechos de recusa, até a auditoria da manhã separar o
        `eleicao_mic_nao_pegou`.)
        **Não há gancho de hotplug-out**, e a posse fica de pé quando o
        controle cai. Enquanto ela ficar, quem publica o estado tem de dizer
        que o dono saiu da mesa em vez de nomeá-lo — é o `eleito_na_mesa` de
        `daemon/subsystems/recado_do_microfone.publicar`, que é remendo do
        RELATO e não cura da posse.

        POR QUE ISTO NÃO É OPCIONAL. Hoje **ninguém devolve o microfone**: não
        há em `src/` observador da fonte padrão, restaurador, nem memória do que
        era antes — a única limpeza é o `remove_configured_dualsense` do shell,
        que só roda em gestos humanos. Sem este caminho, o desfecho padrão de
        ela desconectar o controle é o `.monitor` do sink ou o `auto_null`:
        *"ela desconecta o controle e o sistema passa a gravar o áudio de
        saída"*, que é FONTE-PADRÃO-01/MONITOR-QUE-VENCE-01 inteiro.

        **RESPOSTA VAZIA NÃO VIRA `.monitor`.** Quando não há fonte que se
        sustente — o estado desta bancada hoje, com a webcam fora e as três
        portas analógicas `not available` —, não se elege NADA, o motivo vai
        para a tela, **e a posse não cai**: sem escrita, o padrão do sistema
        continua sendo o canal deste controle.
        """
        nome = melhor_fonte_elegivel()
        if nome is None:
            return ResultadoDaEleicao(
                ok=False,
                motivo=(
                    "não há microfone para onde voltar: nenhuma fonte de "
                    "captura com porta usável nesta máquina. Deixo o padrão "
                    "como está em vez de eleger o monitor da saída, que "
                    "gravaria o som do sistema no lugar da voz"
                ),
            )
        resultado = self._eleger_nome(nome)
        # A POSSE SÓ CAI QUANDO A DEVOLUÇÃO É CONFERIDA — a mesma régua de
        # `eleger_por_uniq`, e agora nos dois sentidos.
        #
        # FATO SUBSTITUÍDO (02/09/2026). Estas duas escritas eram
        # incondicionais, com o comentário *"A POSSE CAI MESMO SEM DESTINO — o
        # controle saiu do ar"*. A premissa era falsa: quando a devolução
        # falha, **nada foi escrito** — sem fonte elegível, sem fonte que se
        # sustente, ou com o `pactl` recusando, o `set-default-source` nunca
        # roda — e o padrão do sistema continua sendo o canal DESTE controle.
        # Dizer que a posse caiu era declarar sucesso pela intenção, que é o
        # *"silêncio não é sucesso"* na forma mais cara que ele tem aqui.
        #
        # Consequência medida no `state_full`: depois de uma devolução recusada
        # o bloco publicava `eleito: null` com o canal ainda no controle — a
        # tela dizendo que ninguém está no ar enquanto o sistema grava por ele.
        #
        # É o que a decisão dela de 02/09 exige por baixo do LED: *"quando a
        # devolução é recusada, o canal continua sendo daquele controle, logo o
        # microfone está no ar, logo a luz fica acesa"*. Luz acesa com posse
        # caída seria o plástico e a tela dando vereditos opostos.
        #
        # E o que a premissa velha temia continua certo, só que ao contrário:
        # a próxima borda deste controle SER lida como "o eleito devolvendo de
        # novo" é o comportamento correto — ele ainda tem o canal e está
        # tentando outra vez; e a borda de outro jogador SER recusa também é,
        # porque o canal de fato não é dele.
        #
        # E A RECUSA NÃO É UMA SÓ — auditoria de 02/09/2026. Esta linha era
        # `if resultado.ok`, e com ela os TRÊS desfechos de `ok=False` ficavam
        # iguais. Dois estão certos (nada foi escrito, o canal continua dele);
        # o TERCEIRO é o `eleicao_mic_nao_pegou`: a escrita foi ACEITA e o
        # ativo relido é um terceiro. Aí o canal não é mais dele, e manter a
        # posse é a mentira de segunda geração no caminho de volta. Quem separa
        # os três é `_o_eleito_saiu_do_ar`, que compara o ativo relido com o
        # NOME do canal dele — e é por isso que `fonte_do_eleito` existe.
        if self._o_eleito_saiu_do_ar(resultado):
            self.eleito = None
            self.fonte_do_eleito = None
        return resultado


def recusa_de_quem_nao_elegeu(eleito: str | None) -> ResultadoDaEleicao:
    """A frase do jogador que apertou o botão e NÃO tem o microfone da mesa.

    MIC-RECUSA-NA-TELA-01 (02/09/2026). Este era o caminho mais calado dos
    três: `daemon/subsystems/hotkey._eleger_ou_devolver` apagava a luz do
    controle e voltava com um `logger.info("mic_da_mesa_mudo_de_quem_nao_
    elegeu")` — **sem motivo nenhum para a tela**. Quem está com o controle na
    mão via a luz apagar e o microfone continuar no vizinho, sem uma palavra.

    A frase mora AQUI, e não no laço do daemon, pela mesma razão que as outras
    cinco: este módulo é o dono do vocabulário da eleição, e `ResultadoDaEleicao`
    é o tipo que a casa já usa para "não deu, e o porquê vai para a tela".
    Escrevê-la no `hotkey.py` criaria a sexta frase fora do lugar das cinco.

    Os DOIS casos são distintos e a pessoa precisa deles separados:

    * ``eleito is None`` — ninguém tomou o microfone da mesa. Não há o que
      devolver, e devolver aqui reelegeria a "melhor fonte" trocando o padrão
      do sistema dela sem que ela tivesse elegido nada;
    * ``eleito`` é outro controle — o canal é de outra pessoa, e o botão só
      apagou a luz de quem apertou.

    **Não nomeia o dono.** O `uniq` é endereço de rádio, não nome de gente; a
    tela sabe traduzi-lo em "P2" (é o mesmo `data-uniq` do card) e o
    ``eleito`` viaja como DADO ao lado da frase, em
    `daemon/subsystems/recado_do_microfone`.
    """
    if eleito is None:
        return ResultadoDaEleicao(
            ok=False,
            motivo=(
                "ninguém está com o microfone da mesa, então não há o que "
                "devolver — este botão só apagou a luz deste controle"
            ),
        )
    return ResultadoDaEleicao(
        ok=False,
        motivo=(
            "o microfone da mesa está com outro controle: só quem elegeu pode "
            "devolvê-lo. Este botão apagou a luz deste controle e não mexeu no "
            "canal de áudio de ninguém"
        ),
    )


def fontes_de_captura_agora() -> list[str]:
    """As sources de captura de DualSense que o PipeWire publica AGORA."""
    rc, saida = _rodar(["pactl", "list", "sources", "short"])
    if rc != 0:
        return []
    return fontes_dualsense(saida)


def casamento_usb_agora(uniqs: list[str]) -> CasamentoUSB | None:
    """O casamento "quem pendura em qual dispositivo USB", montado agora.

    `None` quando não deu para montar (sem `pactl`, saída ilegível) — e quem
    recebe `None` cai nas outras três regras de `escolher_fonte`, que é
    conservador e não inventa dado.
    """
    from hefesto_dualsense4unix.integrations.usb_pai import (
        nos_e_sysfs,
        usb_pai_por_no,
        usb_pai_por_uniq,
    )

    if not uniqs:
        return None
    rc, longa = _rodar(["pactl", "list", "sources"])
    if rc != 0 or not longa.strip():
        return None
    try:
        return CasamentoUSB(
            por_uniq=usb_pai_por_uniq(uniqs),
            por_no=usb_pai_por_no(nos_e_sysfs(longa)),
        )
    except OSError:
        return None


__all__ = [
    "ESPERA_DO_CANAL_PASSOS",
    "ESPERA_DO_CANAL_PASSO_S",
    "EleitorDeMicrofone",
    "ResultadoDaEleicao",
    "_script_conhece",
    "casamento_usb_agora",
    "dizer_no_ar",
    "esquecer_a_palavra",
    "fonte_ativa",
    "fonte_se_sustenta",
    "fontes_de_captura_agora",
    "melhor_fonte_elegivel",
    "pedir_canal",
    "recusa_de_quem_nao_elegeu",
    "registrar_dizedor_do_no_ar",
    "registrar_pedidor_de_canal",
]
