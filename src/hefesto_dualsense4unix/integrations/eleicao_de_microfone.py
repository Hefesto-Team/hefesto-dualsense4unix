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

import contextlib
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    CasamentoUSB,
    escolher_fonte,
    fontes_dualsense,
    fontes_nativas,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_TIMEOUT_S = 3.0

SETTLE_PASSOS = 20
SETTLE_PASSO_S = 0.25

_NADA_DO_PIPEWIRE = "auto_null"

ESPERA_DO_CANAL_PASSOS = 12
ESPERA_DO_CANAL_PASSO_S = 0.25

_PEDIDOR_DE_CANAL: Callable[[str], bool] | None = None


def registrar_pedidor_de_canal(
    pedidor: Callable[[str], bool] | None,
) -> Callable[[str], bool] | None:
    """Instala quem atende pedido de canal. Devolve o anterior, para restaurar."""
    global _PEDIDOR_DE_CANAL
    anterior = _PEDIDOR_DE_CANAL
    _PEDIDOR_DE_CANAL = pedidor
    return anterior


def pedir_canal(uniq: str) -> bool:
    """Pede o canal de captura do controle `uniq`. False = ninguém atendeu."""
    pedidor = _PEDIDOR_DE_CANAL
    if pedidor is None:
        return False
    try:
        return bool(pedidor(uniq))
    except Exception:
        logger.debug("eleicao_mic_pedido_de_canal_falhou", exc_info=True)
        return False


_DIZEDOR_DO_NO_AR: Callable[[str, bool], bool] | None = None

_ESQUECEDOR_DA_PALAVRA: Callable[[str], bool] | None = None

_LEITOR_DA_PALAVRA: Callable[[str], bool | None] | None = None

_GanchosDaPalavra = tuple[
    Callable[[str, bool], bool] | None,
    Callable[[str], bool] | None,
    Callable[[str], bool | None] | None,
]


def registrar_dizedor_do_no_ar(
    dizedor: Callable[[str, bool], bool] | None,
    esquecedor: Callable[[str], bool] | None = None,
    leitor: Callable[[str], bool | None] | None = None,
) -> _GanchosDaPalavra:
    """Instala quem atende a palavra dela. Devolve os anteriores, para restaurar."""
    global _DIZEDOR_DO_NO_AR, _ESQUECEDOR_DA_PALAVRA, _LEITOR_DA_PALAVRA
    anteriores = (_DIZEDOR_DO_NO_AR, _ESQUECEDOR_DA_PALAVRA, _LEITOR_DA_PALAVRA)
    _DIZEDOR_DO_NO_AR = dizedor
    _ESQUECEDOR_DA_PALAVRA = esquecedor
    _LEITOR_DA_PALAVRA = leitor
    return anteriores


def palavra_no_ar(uniq: str) -> bool | None:
    """O que ela disse sobre ESTE microfone. `None` = nada, ou ninguém atende."""
    leitor = _LEITOR_DA_PALAVRA
    if leitor is None:
        return None
    try:
        resposta = leitor(uniq)
    except Exception:
        logger.debug("eleicao_mic_leitura_da_palavra_falhou", exc_info=True)
        return None
    return resposta if isinstance(resposta, bool) else None


def dizer_no_ar(uniq: str, ligado: bool) -> bool:
    """*"Quero/não quero este microfone no ar"*. False = ninguém atendeu."""
    dizedor = _DIZEDOR_DO_NO_AR
    if dizedor is None:
        return False
    try:
        return bool(dizedor(uniq, ligado))
    except Exception:
        logger.debug("eleicao_mic_palavra_dela_falhou", exc_info=True)
        return False


def esquecer_a_palavra(uniq: str) -> bool:
    """Ela deixa de ter dito qualquer coisa sobre este microfone."""
    esquecedor = _ESQUECEDOR_DA_PALAVRA
    if esquecedor is None:
        return False
    try:
        return bool(esquecedor(uniq))
    except Exception:
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
    from hefesto_dualsense4unix.integrations import retrato_do_som

    resposta = retrato_do_som.responder(argv)
    if resposta is not None:
        return (0, resposta.strip()) if isinstance(resposta, str) else (127, "")
    exe = shutil.which(argv[0])
    if exe is None:
        return (127, "")
    try:
        proc = subprocess.run(
            [exe, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            env=_ambiente_c(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return (127, "")
    finally:
        retrato_do_som.escreveu(argv)
    return (proc.returncode, proc.stdout.strip())


_MEMORIA_DO_FIO = threading.local()


@contextlib.contextmanager
def uma_leitura_por_volta() -> Iterator[None]:
    """Neste fio, e só enquanto durar, cada `argv` roda uma vez."""
    antes = getattr(_MEMORIA_DO_FIO, "lidos", None)
    _MEMORIA_DO_FIO.lidos = {}
    try:
        yield
    finally:
        _MEMORIA_DO_FIO.lidos = antes


def _ler(argv: list[str]) -> tuple[int, str]:
    """O `_rodar`, com a memória da volta quando ela está ligada neste fio."""
    lidos: dict[tuple[str, ...], tuple[int, str]] | None = getattr(
        _MEMORIA_DO_FIO, "lidos", None)
    if lidos is None:
        return _rodar(argv)
    chave = tuple(argv)
    if chave not in lidos:
        lidos[chave] = _rodar(argv)
    return lidos[chave]


def _script_do_wireplumber() -> Path | None:
    """O script que é DONO do critério de fonte que se sustenta."""
    from hefesto_dualsense4unix.utils.repo_files import encontrar_arquivo_do_repo

    nome = "fix_wireplumber_default_source.sh"
    achado_na_instalacao = encontrar_arquivo_do_repo(f"scripts/{nome}")
    if achado_na_instalacao is not None:
        return achado_na_instalacao
    achado = shutil.which(nome)
    return Path(achado) if achado else None


def _script_conhece(script: Path, flag: str) -> bool:
    """O script instalado ACEITA esta flag? Se não, não se chama."""
    try:
        texto = script.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return flag in texto


def fonte_se_sustenta(nome: str) -> bool | None:
    """A fonte `nome` para de pé? `None` = não deu para consultar."""
    script = _script_do_wireplumber()
    if script is None or not _script_conhece(script, "--fonte-se-sustenta"):
        return None
    rc, saida = _rodar(["bash", str(script), "--fonte-se-sustenta", nome])
    if rc != 0:
        return None
    return saida.strip() == nome


class ConsultaIndisponivelError(RuntimeError):
    """Não deu para PERGUNTAR ao dono do critério — e isso não é a resposta."""


def outra_captura_elegivel() -> str | None:
    """A melhor captura com porta usável que não é CONTROLE NENHUM, ou `None`.

    Irmã da pergunta do INSTALL (`--melhor-fonte-elegivel` do script), e a
    diferença é o canal por controle (``hefesto_mic_<marca>``): lá ele entra de
    propósito — é o §D.2 da MIC-PADRAO-NO-CABO-01, em que pelo rádio o eleito
    do install é o microfone virtual do controle —, e aqui ele é controle.

    **QUEM PERGUNTA SÃO DOIS**, e a pergunta é a mesma: *"esta máquina tem um
    microfone que a pessoa usa e que não é um DualSense?"*. O nascimento do
    microfone (`daemon/subsystems/hotkey._microfone_que_ja_e_da_maquina`),
    desde 18/09/2026; e a volta do microfone
    (:meth:`EleitorDeMicrofone.devolver_o_microfone`), desde 29/09/2026
    (A-VOLTA-DO-MICROFONE-NAO-ELEGE-CONTROLE-01). Com a pergunta do install, o
    canal do controle cujo nó nasceu primeiro no PipeWire passa por microfone
    da máquina: no nascimento, o segundo controle nunca elegeria na máquina que
    só tem os controles; na volta, calar o único no ar elegia um calado.

    **TRÊS RESPOSTAS, E A TERCEIRA LEVANTA** (18/09/2026): um nome, `None`
    (consultei e não há) ou :class:`ConsultaIndisponivelError` (não deu para
    consultar). Até esta data o *"não deu"* voltava como `None`, e o nascimento
    lia *"não há outro microfone"* e elegia: com a consulta estourando o tempo
    enquanto o `--fonte-se-sustenta` ainda respondia, o controle tomava o
    headset; sem o script, a eleição recusava e a sexta porta deixava o
    microfone MUDO. Levantar em vez de devolver é o que obriga quem pergunta a
    tratar o *"não sei"* — e o único que pergunta trata como *"não eleja"*.

    O script que não conhece a pergunta (produto instalado mais velho que o
    pacote) também levanta, e nunca é chamado: chamar seria uma instalação
    silenciosa — ver :func:`_script_conhece`.
    """
    script = _script_do_wireplumber()
    if script is None:
        raise ConsultaIndisponivelError(
            "o script do WirePlumber não está nesta instalação"
        )
    if not _script_conhece(script, "--outra-captura-elegivel"):
        raise ConsultaIndisponivelError(
            f"{script} não conhece --outra-captura-elegivel (é mais velho que o pacote)"
        )
    rc, saida = _rodar(["bash", str(script), "--outra-captura-elegivel"])
    if rc != 0:
        raise ConsultaIndisponivelError(
            f"--outra-captura-elegivel não respondeu (rc={rc})"
        )
    nome = saida.strip().splitlines()[-1].strip() if saida.strip() else ""
    return nome or None


def fonte_ativa() -> str | None:
    """`pactl get-default-source`, ou `None` quando a resposta não significa nada."""
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
    """O que a eleição conseguiu, e nunca o que ela mandou."""

    ok: bool
    alvo: str | None = None
    ativo: str | None = None
    motivo: str = ""


@dataclass
class EleitorDeMicrofone:
    """Elege por `uniq`, confere relendo o ativo, e sabe o caminho de volta."""

    anterior: str | None = None
    _guardou: bool = field(default=False, repr=False)

    eleito: str | None = None

    #: e o `state_full` publicava `eleito: …011` com `ativo: mic_de_um_terceiro`
    fonte_do_eleito: str | None = None

    def guardar_anterior(self) -> str | None:
        """Guarda o `get-default-source` de antes — UMA vez por sessão."""
        if self._guardou:
            return self.anterior
        self._guardou = True
        self.anterior = fonte_ativa()
        logger.info("eleicao_mic_guardou_anterior", anterior=self.anterior)
        return self.anterior


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
        if resultado.ok:
            self.eleito = uniq
            self.fonte_do_eleito = alvo
        elif self._o_eleito_saiu_do_ar(resultado):
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
        """A releitura do ATIVO prova que o canal do eleito deixou de ser o padrão?"""
        if resultado.ok:
            return True
        if resultado.ativo is None or self.fonte_do_eleito is None:
            return False
        return resultado.ativo != self.fonte_do_eleito

    def _eleger_nome(self, alvo: str) -> ResultadoDaEleicao:
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
        """Espera o grafo assentar e relê o ATIVO — nunca o `configured`."""
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
        """`eleger_por_uniq` juntando os dados do PipeWire e do sysfs sozinho."""
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
        """As fontes de agora, PEDINDO o canal deste controle se ele faltar."""
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


    def passar_o_padrao(
        self,
        no_ar: list[str],
        conectados: list[str],
        calou: str | None = None,
    ) -> ResultadoDaEleicao:
        """Para onde vai a fonte padrão quando quem falava saiu do ar.

        A-VOLTA-DO-MICROFONE-NAO-ELEGE-CONTROLE-01 (29/09/2026). É UMA pergunta
        só, e este método é o dono dela. As duas portas que a fazem o chamam: o
        botão do microfone do eleito
        (`daemon/subsystems/hotkey._passar_o_padrao_ou_devolver`, o plástico e
        o 🎙 da tela) e o nó que morre
        (`daemon/subsystems/bt_mic._devolver_a_fonte_padrao`, pelo laço do
        daemon). A resposta, em ordem:

        (a) **quem está no ar**, na ordem que `no_ar` traz (do mais novo ao
            mais velho, só quem está na mesa), pela `eleger_o_controle` de
            sempre, com a releitura do ativo e as recusas dela;
        (b) **sem ninguém no ar, a volta à máquina**, por
            :meth:`devolver_o_microfone`, que pergunta
            :func:`outra_captura_elegivel`;
        (c) **sem as duas, o padrão fica onde está.** Nada se escreve.

        Um canal de controle vira o padrão só por (a), pela ida
        (`eleger_o_controle`) e pelo nascimento no ar. A ordem do no ar é lida
        por quem chama, no laço do daemon: aqui chega uma lista, e o
        `MicrofonesNoAr` segue no `hotkey.py`.

        **O «FICA» É UM SÓ, E CADA PORTA O LÊ PELO QUE ELA É.** `calou` é o
        `uniq` de quem apertou para se calar, e só o botão o passa:

        * no botão, o ato é de calar e a palavra dela já foi dita. O padrão
          fica no canal que ela calou, que grava silêncio por escolha dela; a
          posse do eleito cai aqui, e o ato está FEITO (``ok=True``, sem
          frase, com o ativo relido). É a decisão dela de 19/09
          (A-LUZ-DO-MIC-ESPELHA-O-BOTAO-01): a luz é o estado do microfone
          dela, e mudo é apagada;
        * no nó que morre (sem `calou`), o buraco continua: ``ok=False`` com o
          motivo, que vai para o diário. Sem candidato real, eleger outra fonte
          não é a cura (a correção de rumo da SOM-PAINEL-01, 17/09/2026).

        **O QUE A CURA NÃO PROMETE:** com todos os controles calados e nenhum
        outro microfone, o único padrão que não é monitor é um canal calado. O
        que se garante é que é o que ela calou, e nunca um que ninguém escolheu.
        """
        for candidato in no_ar:
            passado = self.eleger_o_controle(candidato, list(conectados))
            logger.info(
                "mic_da_mesa_padrao_passado",
                de=calou,
                para=candidato,
                ok=bool(passado.ok),
                motivo=passado.motivo,
            )
            if passado.ok:
                return passado
        volta = self.devolver_o_microfone()
        if volta.ok or volta.alvo is not None:
            return volta
        ativo = fonte_ativa()
        if calou is None:
            logger.info("eleicao_mic_padrao_fica", ativo=ativo, motivo=volta.motivo)
            return ResultadoDaEleicao(ok=False, ativo=ativo, motivo=volta.motivo)
        from hefesto_dualsense4unix.integrations.fontes_de_captura import so_hex

        quem = so_hex(calou)
        if quem and self.eleito is not None and so_hex(self.eleito) == quem:
            self.eleito = None
            self.fonte_do_eleito = None
        logger.info(
            "eleicao_mic_padrao_fica", calou=calou, ativo=ativo, motivo=volta.motivo
        )
        return ResultadoDaEleicao(ok=True, ativo=ativo)

    def devolver_o_microfone(self) -> ResultadoDaEleicao:
        """A VOLTA À MÁQUINA: o padrão vai a uma captura que não é controle nenhum."""
        try:
            nome = outra_captura_elegivel()
        except ConsultaIndisponivelError as exc:
            return ResultadoDaEleicao(ok=False, motivo=str(exc))
        if nome is None:
            return ResultadoDaEleicao(
                ok=False,
                motivo=(
                    "não há microfone para onde voltar: nenhuma fonte de "
                    "captura com porta usável que não seja um controle. Deixo o "
                    "padrão como está em vez de eleger o monitor da saída, que "
                    "gravaria o som do sistema no lugar da voz"
                ),
            )
        resultado = self._eleger_nome(nome)
        if self._o_eleito_saiu_do_ar(resultado):
            self.eleito = None
            self.fonte_do_eleito = None
        return resultado


def recusa_de_quem_nao_elegeu(eleito: str | None) -> ResultadoDaEleicao:
    """A frase do jogador que apertou o botão e NÃO tem o microfone da mesa."""
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
    return _fontes_de_captura_ou_nada() or []


def _fontes_de_captura_ou_nada() -> list[str] | None:
    """Como `fontes_de_captura_agora`, mas `None` quando o `pactl` não respondeu."""
    rc, saida = _rodar(["pactl", "list", "sources", "short"])
    if rc != 0:
        return None
    return fontes_dualsense(saida)


def canal_publicado(uniq: str, conectados: list[str]) -> bool | None:
    """O canal de captura DESTE controle está publicado agora? `None` = não sei.

    OS-QUATRO-NO-AR-01 (13/09/2026). Com os quatro microfones no ar ao mesmo
    tempo, *"perder o padrão"* deixou de tirar alguém do ar; o que tira é o
    canal daquele controle sumir DE FATO — a ponte de rádio caiu e não voltou,
    ou o controle saiu da mesa. Quem pergunta é
    `daemon/subsystems/hotkey._conferir_quem_saiu_do_ar`, e a pergunta é a de
    sempre, pelo dono de sempre (`escolher_fonte`).

    **AS TRÊS RESPOSTAS SÃO TRÊS COISAS:**

    * `True` — há um nó atribuível a este controle;
    * `False` — o `pactl` respondeu e NÃO há. Só se afirma quando o nome dos
      nós basta para decidir: todo nó de DualSense publicado carrega identidade
      no nome (regras 0, 1 e 2), ou o casamento por USB foi montado;
    * `None` — o `pactl` não respondeu, ou há nó ALSA anônimo e o casamento
      por USB não saiu. **"Não sei" nunca vira "saiu"**: foram 47 minutos de
      servidor mudo em 13/09/2026, e um microfone que caísse do ar por falta de
      resposta seria o produto calando alguém sem gesto nenhum.
    """
    from hefesto_dualsense4unix.integrations.fontes_de_captura import identidade_no_nome

    fontes = _fontes_de_captura_ou_nada()
    if fontes is None:
        return None
    if not fontes:
        return False
    if escolher_fonte(fontes, uniq, [], None) is not None:
        return True
    usb = casamento_usb_agora(list(conectados))
    if usb is None:
        if all(identidade_no_nome(fonte) for fonte in fontes):
            return False
        return None
    return escolher_fonte(fontes, uniq, list(conectados), usb) is not None


def microfone_nativo_no_ar(uniq: str, conectados: list[str]) -> bool | None:
    """Há fonte de captura NATIVA para `uniq` agora? `None` = não sei."""
    return _a_nativa_deste(uniq, conectados)[0]


def fonte_nativa_do_controle(uniq: str, conectados: list[str]) -> str | None:
    """O NOME do nó de captura nativo deste controle agora. TRÊS respostas.

    O-GANHO-DO-MIC-TEM-DONO-01, 20/09/2026 — e ela nasce porque perguntar
    *"qual nó é o microfone deste controle"* ao daemon dá a resposta ERRADA
    para esta pergunta: o ``canal_fonte`` do ``state_full`` é o nó que o
    produto ELEGEU, e a regra 0 de :func:`escolher_fonte` faz dele o nosso
    ``hefesto_mic_<hex6>`` — **inclusive no cabo**. Medido na mesa dela em
    20/09, com um DualSense no fio e três no ar: os QUATRO responderam
    ``hefesto_mic_…``, e nenhum deles tem placa ALSA.

    Quem tem placa ALSA é a fonte NATIVA, e é ela que este nome devolve.

    **AS TRÊS SÃO TRÊS COISAS**, com a mesma disciplina da irmã acima — e
    colapsar as duas primeiras é o defeito que ela existe para não cometer:

    * o NOME — há nó nativo, e é este;
    * ``""`` — o ``pactl`` respondeu e não há nó nativo para este controle (o
      rádio, que não publica placa nenhuma);
    * ``None`` — **não sei**: o ``pactl`` não respondeu, ou o censo de USB não
      pôde ser montado. Quem recebe isto não pode dizer *"não há"* na tela.

    A irmã :func:`microfone_nativo_no_ar` divide o mesmo corpo
    (:func:`_a_nativa_deste`): duas implementações da mesma busca é como esta
    casa fabrica divergência silenciosa.
    """
    ha, no = _a_nativa_deste(uniq, conectados)
    return None if ha is None else no


def _a_nativa_deste(uniq: str, conectados: list[str]) -> tuple[bool | None, str]:
    """``(há nativa?, nome)`` — o corpo único das duas perguntas acima."""
    rc, saida = _ler(["pactl", "list", "sources", "short"])
    if rc != 0:
        return (None, "")
    nativas = fontes_nativas(saida)
    if not nativas:
        return (False, "")
    no = escolher_fonte(nativas, uniq, [], None)
    if no is not None:
        return (True, no)
    usb = casamento_usb_agora(list(conectados))
    if usb is None:
        return (None, "")
    no = escolher_fonte(nativas, uniq, list(conectados), usb)
    return (no is not None, no or "")


def casamento_usb_agora(uniqs: list[str]) -> CasamentoUSB | None:
    """O casamento "quem pendura em qual dispositivo USB", montado agora."""
    from hefesto_dualsense4unix.integrations.usb_pai import (
        nos_e_sysfs,
        usb_pai_por_no,
        usb_pai_por_uniq,
    )

    if not uniqs:
        return None
    rc, longa = _ler(["pactl", "list", "sources"])
    if rc != 0 or not longa.strip():
        return None
    try:
        return CasamentoUSB(
            por_uniq=usb_pai_por_uniq(uniqs),
            por_no=usb_pai_por_no(nos_e_sysfs(longa)),
        )
    except OSError:
        return None


#: As chaves do `default-nodes` do WirePlumber que guardam a escolha dela.
CHAVE_DA_FONTE_GRAVADA = "default.configured.audio.source"
CHAVE_DA_SAIDA_GRAVADA = "default.configured.audio.sink"

_ESCOLHAS_JA_PASSADAS: set[tuple[str, str]] = set()
_TRAVA_DA_PASSAGEM = threading.Lock()


def passar_a_escolha_gravada_ao_nome_novo(
    uniq: str,
    novo: str,
    *,
    prefixo: str,
    saida: bool = False,
    ler: Callable[[str], str | None] | None = None,
    rodar: Callable[[list[str]], tuple[int, str]] | None = None,
) -> bool:
    """A escolha que ela gravou no nome VELHO deste controle passa ao nome novo. Uma vez.

    OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01 (02/10/2026): os nós do controle
    trocaram o rabo do endereço pela marca do aparelho, e o WirePlumber lembra
    a escolha pelo nome. Na primeira subida do nó novo (``novo``, de
    ``prefixo``), se a fonte padrão gravada (ou a saída, com ``saida=True``) é
    o nome velho DAQUELE controle (``prefixo`` + os seis últimos hex do
    ``uniq``), ela passa ao nome novo, com uma linha no diário. A de outro
    controle não se toca, e a escolha que não é de controle nenhum também não.
    Devolve se passou. Nunca levanta.
    """
    from hefesto_dualsense4unix.core.system_check import (
        escolha_configurada_do_wireplumber,
    )
    from hefesto_dualsense4unix.integrations.fontes_de_captura import so_hex

    rabo = so_hex(uniq)[-6:]
    if len(rabo) < 6 or not novo:
        return False
    papel = "sink" if saida else "source"
    chave_da_vez = (f"{papel}:{prefixo}", rabo)
    with _TRAVA_DA_PASSAGEM:
        if chave_da_vez in _ESCOLHAS_JA_PASSADAS:
            return False
        _ESCOLHAS_JA_PASSADAS.add(chave_da_vez)
    ler_a_escolha = ler or escolha_configurada_do_wireplumber
    try:
        gravada = ler_a_escolha(CHAVE_DA_SAIDA_GRAVADA if saida else CHAVE_DA_FONTE_GRAVADA)
    except Exception:
        return False
    if not gravada or gravada.strip().lower() != f"{prefixo}{rabo}":
        return False
    escrever = rodar or _rodar
    try:
        rc, _ = escrever(["pactl", f"set-default-{papel}", novo])
    except Exception:
        rc = -1
    logger.info(
        "escolha_gravada_passou_ao_nome_novo", papel=papel, para=novo, ok=rc == 0
    )
    return rc == 0


__all__ = [
    "CHAVE_DA_FONTE_GRAVADA",
    "CHAVE_DA_SAIDA_GRAVADA",
    "ESPERA_DO_CANAL_PASSOS",
    "ESPERA_DO_CANAL_PASSO_S",
    "ConsultaIndisponivelError",
    "EleitorDeMicrofone",
    "ResultadoDaEleicao",
    "_script_conhece",
    "canal_publicado",
    "casamento_usb_agora",
    "dizer_no_ar",
    "esquecer_a_palavra",
    "fonte_ativa",
    "fonte_se_sustenta",
    "fontes_de_captura_agora",
    "outra_captura_elegivel",
    "palavra_no_ar",
    "passar_a_escolha_gravada_ao_nome_novo",
    "pedir_canal",
    "recusa_de_quem_nao_elegeu",
    "registrar_dizedor_do_no_ar",
    "registrar_pedidor_de_canal",
    "uma_leitura_por_volta",
]
