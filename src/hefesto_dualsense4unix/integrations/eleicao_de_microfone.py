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
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
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
        6. só devolve `ok=True` se o ativo relido for o alvo.
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
        return resultado

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
        """
        fontes = fontes_de_captura_agora()
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
            usb=casamento_usb_agora(uniqs_conectados),
        )

    # -- o caminho de volta (item 6 dela) ---------------------------------

    def devolver_o_microfone(self) -> ResultadoDaEleicao:
        """O controle eleito saiu do ar: elege a melhor fonte que NÃO é ele.

        **QUEM CHAMA, MEDIDO (02/09/2026):** um só — o ramo do botão do
        microfone em `daemon/subsystems/hotkey._eleger_ou_devolver`, quando o
        ELEITO vai a mudo. Este docstring dizia *"quando o controle eleito
        passa a MUDO, cai do rádio/cabo, ou a ponte de microfone dele cai"*, e
        as duas últimas eram falsas: `grep -rn "devolver_o_microfone" src/`
        devolve esta definição e aquela única chamada, e as DUAS escritas de
        `self.eleito` neste módulo são caminhos de eleição CONFERIDA — a de
        `eleger_por_uniq` e a deste método. (Eram três até 02/09, quando as
        duas incondicionais daqui viraram uma condicionada ao `ok`.)
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
        if resultado.ok:
            self.eleito = None
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
    "EleitorDeMicrofone",
    "ResultadoDaEleicao",
    "_script_conhece",
    "casamento_usb_agora",
    "fonte_ativa",
    "fonte_se_sustenta",
    "fontes_de_captura_agora",
    "melhor_fonte_elegivel",
    "recusa_de_quem_nao_elegeu",
]
