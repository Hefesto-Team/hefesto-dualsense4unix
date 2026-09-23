"""gesto_de_pareamento.py — parear um controle PELO HEFESTO.

PONTE-SEM-CHAMADOR-01 (20/09/2026). ``scripts/bt_ponte_privilegiada.sh`` está
instalado como root, o ``/etc/sudoers.d/49-hefesto-bt-ponte`` dá ``NOPASSWD``
para os seus verbos e o ``hefesto-bt-agent.service`` que o ``Pair()`` exige está
ativo — e **nenhuma linha de Python jamais chamou ``descobrir`` nem ``parear``**.
É a ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ`` na forma mais cara que esta casa já
teve: o transporte inteiro de pé, o privilégio concedido e conferido, e o último
palmo faltando. Resíduo de sudoers é o pior tipo de resíduo — é privilégio
concedido a um caminho que ninguém usa.

POR QUE ISTO É A PEÇA CENTRAL, E NÃO UM BOTÃO A MAIS
====================================================
A pergunta dela foi:

    *"a ideia nesse caso não é darmos prioridade pro hefesto? e garantirmos a
    conexão por lá e controlar a conexão melhor que o gerenciador padrão que
    temos no cosmic?"*

Se ela parear um controle **por aqui**, ela nunca abre a tela de Bluetooth do
COSMIC para um controle — e a varredura de terceiro, que custa de 32% a 43% dos
pacotes do adaptador que a hospeda, simplesmente não acontece. A posse do rádio
começa neste arquivo, não numa reserva contra a varredura alheia.

O QUE ESTE MÓDULO FAZ, E O QUE ELE NÃO FAZ
===========================================
Faz duas coisas: abre uma janela de busca no adaptador escolhido e devolve os
candidatos conforme eles aparecem; e pareia UM endereço, quando alguém pedir.

**Não escolhe por ela, e não pareia sozinho.** O gesto físico do controle —
segurar PS + Create até a barra piscar — não se automatiza, e um módulo que
pareasse o primeiro candidato que visse poderia casar o fone da vizinha com o
adaptador dela. Quem escolhe é quem está olhando; este arquivo só sabe abrir a
janela, listar e obedecer.

A JANELA É PROCESSO, E A LEITURA É FIO PRÓPRIO
===============================================
``descobrir`` **bloqueia** pelos segundos que recebe. Chamá-lo no tique da aba
congelaria a janela inteira — é a família do defeito de 15/09/2026 (*"as DUAS
VIAGENS de IPC são SÍNCRONAS — elas seguram o laço do GTK inteiro"*), e a cura
já está escrita na mesma aba, em ``_pedir_o_exame_de_entrada``. Por isso
:class:`JanelaDeBusca` põe a ponte num subprocesso e a leitura num fio
``daemon``: o laço do GTK nunca espera por rádio.

E O ``parear`` TEM DE CORRER DENTRO DA JANELA
==============================================
O ``Pair()`` do BlueZ precisa de um objeto ``org.bluez.Device1``, e o BlueZ
recolhe os dispositivos que a varredura achou quando ela termina. Parear depois
de a janela fechar é chamar um caminho D-Bus que pode já não existir. Por isso
:meth:`JanelaDeBusca.parear` **recusa com motivo** quando a janela fechou, em
vez de tentar e falhar com a mensagem do BlueZ — e por isso a ponte devolve os
candidatos EM FLUXO, para que haja quem parear enquanto a janela vive.

AS TRÊS DISCIPLINAS, AS MESMAS DE ``gesto_de_reconexao.py``
============================================================
* **Nunca levanta.** Toda saída é um :class:`Resultado`; ponte ausente, ``sudo``
  sem regra, erro do processo e teto de tempo colapsam em
  :data:`ESTADO_NAO_DEU`, que é uma resposta e não uma exceção;
* **"não deu" nunca é "não achei"** — o quarto estado é obrigatório. Uma
  varredura que não rodou tem de dizer isso, porque lista vazia lida como
  "ninguém apareceu" manda a pessoa repetir um gesto que nunca foi medido;
* **Nenhum endereço inteiro sai numa frase.** O endereço cheio existe para ser
  argumento da ponte; o que vai para a tela e para o diário é
  :attr:`Candidato.mascara`.

PELO DONO DO BLUEZ E PELO AGENTE NOSSO (BLUEZ-UM-DONO-01, 23/09/2026)
======================================================================
Com o dono do D-Bus vivo (``bluez_dbus.DonoVivo``), a janela é NOSSA: o
``StartDiscovery`` sai da conexão do dono — a busca é POR CLIENTE e morre com
quem a abriu —, os candidatos saem da foto do ``ObjectManager``, e o ``Pair``
sai pela mesma conexão, onde mora o ``Agent1`` próprio (R5): o pareamento que
ELA inicia é atendido por nós, sem virar o agente padrão. A ponte root
(``descobrir``/``parear``) fica de PISO, para quando o dono não está vivo — e
o ``hefesto-bt-agent`` atende o que chega sozinho.

Nos dois caminhos, o que ESCREVE no rádio entra na trava comum
(``diario_do_radio``). O ``StopDiscovery`` é a única exceção: ele solta o
rádio, e esperar alguém para soltá-lo manteria a busca de pé.

QUEM É CONTROLE SE PERGUNTA À CLASSE, NUNCA AO NOME
====================================================
Antes de parear, um candidato não tem ``hidraw``, não tem ``HID_UNIQ`` e não tem
nó de som — não há propriedade de posse a consultar, que é o que esta casa
prefere desde a decisão dela sobre os nós de áudio. O que existe é a *class of
device* do Bluetooth, que o próprio aparelho anuncia e o BlueZ publica em
``org.bluez.Device1.Class``. **Medido na mesa dela em 20/09/2026**: os seis
objetos de DualSense do BlueZ respondem ``u 9480`` (0x2508) — periférico
(classe maior 0x05), gamepad (classe menor 0x02). Casar pelo nome faria o
produto depender do rótulo que o firmware escreve, e o rótulo é de terceiro.
"""

from __future__ import annotations

import contextlib
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations.conexao_zumbi import (
    PONTE_INSTALADA,
    PontePrivilegiada,
    mac_limpo,
)
from hefesto_dualsense4unix.integrations.gesto_de_reconexao import mascarar
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Como este gesto assina na trava e no diário comuns do rádio.
QUEM = "pareamento"

#: Quanto tempo a janela de busca fica aberta, por padrão. Trinta segundos é o
#: que cabe entre segurar PS + Create e a barra piscar sem a pessoa achar que
#: travou — e é bem menos que o teto de 120 s do lado de lá, que existe porque
#: janela sem teto é root parado.
SEGUNDOS_DA_JANELA = 30

#: O teto do outro lado (``bt_ponte_privilegiada.sh``: ``SEGUNDOS_MAX``).
#: Repetido aqui de propósito: mandar 121 faria a ponte recusar com código 2, e
#: recusar antes de gastar um ``sudo`` é mais honesto que descobrir depois.
SEGUNDOS_MAX = 120

#: Teto de tempo para o ``parear``, em segundos. O verbo do outro lado já põe
#: 45 s no ``Pair()``; este é a folga de fora, pelo mesmo motivo que o de lá é
#: cinto do ``bluetoothctl``: quem fica pendurado é um processo com ``sudo``.
ESPERA_DO_PAREAR_S = 60.0

# --- a classe do aparelho ----------------------------------------------------
#
# *Class of device* do Bluetooth: 24 bits, dos quais os bits 12-8 são a classe
# maior e os bits 7-2 a menor. Periférico com tipo de gamepad é o que um
# controle anuncia, e é o que o BlueZ usa para escolher o ícone `input-gaming`.

#: Bits 12-8: `0x05` é *Peripheral*.
CLASSE_MAIOR_PERIFERICO = 0x05

#: Bits 5-2 da classe menor: `0x01` é *Joystick* e `0x02` é *Gamepad*. Os dois
#: entram — o Pro Controller e o 8BitDo desta casa não são DualSense, e o
#: produto os atende.
CLASSES_MENORES_DE_CONTROLE = (0x01, 0x02)

#: Os quatro estados da busca. Nenhum é acento: são chaves de máquina.
ESTADO_ACHOU = "achou"
ESTADO_NINGUEM = "ninguem"  # (noqa-acento): chave de máquina
ESTADO_SEM_PORTA = "sem_porta"
ESTADO_NAO_DEU = "nao_deu"  # (noqa-acento): chave de máquina

#: Os do pareamento. `ja_pareado` não é sucesso nem falha: é o caso comum de um
#: controle que já tem bond NESTE adaptador, e mandá-la repetir PS + Create por
#: causa dele seria pedir trabalho por nada.
ESTADO_PAREOU = "pareou"
ESTADO_JA_PAREADO = "ja_pareado"  # (noqa-acento): chave de máquina
ESTADO_JANELA_FECHADA = "janela_fechada"

FRASE_NINGUEM = (
    "Nenhum controle apareceu na busca. Segure PS + Create no controle até a "
    "barra piscar e procure de novo."
)
FRASE_SEM_PORTA = "O Hefesto ainda não pode parear por aqui nesta máquina: {motivos}."
FRASE_NAO_DEU = (
    "Não consegui abrir a busca no Bluetooth, então não sei se havia algum "
    "controle esperando. Nada foi mudado."
)
FRASE_PAREOU = "Controle pareado neste adaptador. Ele já pode conectar sozinho."
FRASE_JA_PAREADO = "Este controle já estava pareado neste adaptador."
FRASE_JANELA_FECHADA = (
    "A busca já tinha terminado quando o pareamento foi pedido. Procure de novo "
    "e escolha o controle enquanto a busca estiver aberta."
)
FRASE_NAO_PAREOU = (
    "Não consegui parear este controle. Ele ainda está em PS + Create, com a "
    "barra piscando?"
)


def e_controle(classe: int | None) -> bool:
    """Esta *class of device* é a de um controle? ``None`` (ausente) é ``False``.

    A ausência não é dúvida a favor: um aparelho que não publica classe é, na
    prática, um aparelho só-LE, e o controle desta casa fala BR/EDR. Chutar que
    sim colocaria o fone da vizinha na lista de controles dela.
    """
    if classe is None:
        return False
    if (classe >> 8) & 0x1F != CLASSE_MAIOR_PERIFERICO:
        return False
    return ((classe >> 2) & 0x0F) in CLASSES_MENORES_DE_CONTROLE


@dataclass(frozen=True)
class Candidato:
    """Um aparelho que a varredura achou. Imutável: é uma foto, não estado."""

    #: O endereço INTEIRO, em minúsculas. Ele existe para ser argumento da
    #: ponte, e é o único lugar do módulo onde ele aparece inteiro.
    endereco: str
    #: O nome que o BlueZ publica. Vem de terceiro — já higienizado do outro
    #: lado, e nunca usado para decidir nada.
    nome: str = ""
    #: Este endereço já tem bond NESTE adaptador?
    ja_pareado: bool = False
    #: A *class of device*, ou ``None`` quando o BlueZ não a publica.
    classe: int | None = None

    @property
    def mascara(self) -> str:
        """O endereço com os octetos 4 e 5 zerados — o que vai para a tela."""
        return mascarar(self.endereco)

    @property
    def e_controle(self) -> bool:
        """Pergunta à classe, não ao nome. Ver :func:`e_controle`."""
        return e_controle(self.classe)


@dataclass(frozen=True)
class Resultado:
    """O que aconteceu. Imutável, e nunca uma exceção."""

    #: Um dos ``ESTADO_*``.
    estado: str
    #: A frase que a tela mostra, em português e escrita para ela.
    porque: str
    #: Os candidatos, quando houve busca. Vazio nos outros estados.
    candidatos: tuple[Candidato, ...] = ()

    @property
    def deu(self) -> bool:
        """A operação chegou ao fim sabendo o que aconteceu?

        :data:`ESTADO_NINGUEM` conta: uma busca que rodou e não achou ninguém
        SABE que não achou. :data:`ESTADO_NAO_DEU` não conta, e essa é a linha
        inteira deste módulo — um ``False`` aqui significa *"não sei"*, e quem
        chama não pode lê-lo como *"não havia"*.
        """
        return self.estado not in (ESTADO_NAO_DEU, ESTADO_SEM_PORTA)

    @property
    def controles(self) -> tuple[Candidato, ...]:
        """Só os candidatos que anunciam ser controle."""
        return tuple(c for c in self.candidatos if c.e_controle)


def ler_candidato(linha: str) -> Candidato | None:
    """Uma linha de TSV da ponte vira um :class:`Candidato`, ou ``None``.

    O contrato é ``MAC \\t NOME \\t novo|pareado \\t CLASSE``. Recusar em vez de
    adivinhar é deliberado: o endereço vira argumento de um comando
    privilegiado, e o que não é um endereço tem de sair como ``None``, nunca
    como um endereço aproximado. É a mesma régua de
    ``conexao_zumbi.mac_limpo``, e é dela que este módulo a pega.
    """
    partes = linha.rstrip("\n").split("\t")
    if not partes:
        return None
    endereco = mac_limpo(partes[0].strip())
    if endereco is None:
        return None
    nome = partes[1].strip() if len(partes) > 1 else ""
    ja_pareado = len(partes) > 2 and partes[2].strip() == "pareado"
    classe: int | None = None
    if len(partes) > 3:
        bruto = partes[3].strip()
        if bruto.isdigit():
            classe = int(bruto)
    return Candidato(endereco=endereco, nome=nome, ja_pareado=ja_pareado, classe=classe)


#: O que abre um processo: recebe a linha de comando e devolve algo com
#: ``stdout`` (linhas), ``poll()``, ``terminate()``, ``kill()`` e ``wait()``. É
#: por este tipo que o módulo inteiro fica exercitável sem ponte instalada, sem
#: ``sudo`` e sem adaptador na mesa.
Abrir = Callable[[Sequence[str]], "subprocess.Popen[str]"]

#: O que roda um comando até o fim e devolve ``(código, stderr)``. Mesma razão.
Correr = Callable[[Sequence[str]], "tuple[int, str]"]


def _segundos_validos(segundos: int) -> int:
    """Corta para a faixa que a ponte aceita (1 a :data:`SEGUNDOS_MAX`)."""
    return max(1, min(SEGUNDOS_MAX, int(segundos)))


def _abrir_de_verdade(argumentos: Sequence[str]) -> subprocess.Popen[str]:
    """Abre a ponte de verdade, com a saída em linhas."""
    return subprocess.Popen(
        list(argumentos),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def _dono_que_pareia(dono: bluez_dbus.LeitorDoBluez | None) -> bluez_dbus.LeitorDoBluez | None:
    """O dono do BlueZ, se ele pode manter uma busca e atender um ``Pair``.

    Só o dono VIVO pode: a busca é por cliente e morre com um ``busctl`` que
    sai, e o agente próprio precisa de uma conexão que fica.
    """
    leitor = dono if dono is not None else bluez_dbus.dono()
    return leitor if leitor.atende_o_proprio_pareamento else None


def _limpo(nome: str) -> str:
    """O nome de terceiro sem caractere de controle — o que a ponte fazia no TSV."""
    return " ".join("".join(c if c.isprintable() else " " for c in nome).split())


def _correr_de_verdade(argumentos: Sequence[str]) -> tuple[int, str]:
    """Roda a ponte até o fim. Os três jeitos de não dar viram ``(1, motivo)``."""
    try:
        feito = subprocess.run(
            list(argumentos),
            capture_output=True,
            text=True,
            timeout=ESPERA_DO_PAREAR_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as erro:
        return 1, f"a ponte não respondeu: {erro}"
    return feito.returncode, (feito.stderr or "").strip()


class JanelaDeBusca:
    """Uma janela de busca aberta num adaptador, lida em fio próprio.

    Use como gerenciador de contexto — a saída fecha a janela mesmo quando
    alguém levanta no meio, e uma varredura esquecida aberta é justamente o
    custo de rádio que este módulo existe para evitar.
    """

    def __init__(
        self,
        adaptador: str,
        segundos: int = SEGUNDOS_DA_JANELA,
        *,
        caminho: str = PONTE_INSTALADA,
        abrir: Abrir | None = None,
        correr: Correr | None = None,
        dono: bluez_dbus.LeitorDoBluez | None = None,
    ) -> None:
        self.adaptador = mac_limpo(adaptador) or ""
        self.segundos = _segundos_validos(segundos)
        self.caminho = caminho
        self._abrir = abrir or _abrir_de_verdade
        self._correr = correr or _correr_de_verdade
        self._processo: subprocess.Popen[str] | None = None
        self._fio: threading.Thread | None = None
        self._tranca = threading.Lock()
        self._achados: list[Candidato] = []
        self._vistos: set[str] = set()
        #: O dono vivo, quando a janela é nossa; ``None`` quando é a da ponte.
        #: Quem injeta a ponte (``abrir``/``correr``) escolhe a ponte.
        self._dono = _dono_que_pareia(dono) if abrir is None and correr is None else None
        self._no_do_adaptador = ""
        self._fim: float | None = None
        self._fechada = False
        self._tranca_de_fechar = threading.Lock()
        self._relogio: threading.Timer | None = None

    @property
    def pelo_dono(self) -> bool:
        """A janela é a NOSSA (dono vivo e agente próprio), e não a da ponte."""
        return self._dono is not None

    # -- abrir e fechar -------------------------------------------------------

    def abrir_a_janela(self) -> str:
        """Começa a varredura. Devolve ``""`` quando deu, ou o motivo.

        Nunca levanta: um erro ao abrir o processo vira motivo, e o motivo vira
        :data:`ESTADO_NAO_DEU` lá em cima.
        """
        if not self.adaptador:
            return "o endereço do adaptador não tem forma de endereço"
        if self._dono is not None:
            return self._abrir_pelo_dono(self._dono)
        if self._processo is not None:
            return ""
        argumentos = [
            "sudo",
            "-n",
            "--",
            self.caminho,
            "descobrir",
            self.adaptador,
            str(self.segundos),
        ]
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        try:
            # A trava cobre o NASCIMENTO da busca da ponte: ela não começa a
            # varrer no meio do gesto de outro motor.
            with bluez_dbus.na_trava(QUEM):
                self._processo = self._abrir(argumentos)
        except TravaOcupadaError as ocupada:
            return f"o rádio estava ocupado: {ocupada}"
        except (OSError, ValueError) as erro:
            return f"não consegui abrir a busca: {erro}"
        self._fio = threading.Thread(
            target=self._ler, name="hefesto-busca-de-controle", daemon=True
        )
        self._fio.start()
        logger.info(
            "pareamento_janela_aberta",
            adaptador=mascarar(self.adaptador),
            segundos=self.segundos,
        )
        return ""

    def _abrir_pelo_dono(self, dono: bluez_dbus.LeitorDoBluez) -> str:
        """``StartDiscovery`` pela conexão do dono, com um relógio que a fecha."""
        if self._no_do_adaptador:
            return ""
        no = dono.caminho_do_adaptador(self.adaptador)
        if no is None:
            return "o adaptador não está na mesa (plugado e ligado?)"
        escrita = dono.comecar_busca(no, quem=QUEM)
        if not escrita.feita:
            return f"o BlueZ não abriu a busca: {escrita.erro or escrita.mensagem}"
        self._no_do_adaptador = no
        self._fim = time.monotonic() + self.segundos
        # A busca é da conexão do dono, que vive o processo inteiro: sem este
        # relógio, uma janela esquecida varreria até o daemon sair.
        self._relogio = threading.Timer(self.segundos, self.fechar)
        self._relogio.daemon = True
        self._relogio.start()
        logger.info(
            "pareamento_janela_aberta",
            adaptador=mascarar(self.adaptador),
            segundos=self.segundos,
            pelo_dono=True,
        )
        return ""

    def _colher(self) -> None:
        """Os aparelhos que a foto do dono tem sob este adaptador, em ordem."""
        dono = self._dono
        if dono is None or not self._no_do_adaptador:
            return
        for aparelho in dono.aparelhos(adaptador=self._no_do_adaptador) or ():
            with self._tranca:
                if aparelho.endereco in self._vistos:
                    continue
                self._vistos.add(aparelho.endereco)
                self._achados.append(
                    Candidato(
                        endereco=aparelho.endereco,
                        nome=_limpo(aparelho.nome),
                        ja_pareado=bool(aparelho.pareado),
                        classe=aparelho.classe,
                    )
                )

    def _ler(self) -> None:
        """O fio que lê o fluxo da ponte. Engole tudo, de propósito.

        O ``except`` largo é o contrato do fio: uma exceção aqui não tem quem a
        receba — o fio morre calado e o traceback vai para o ``stderr`` de
        ninguém. Engolir e deixar a lista como está devolve a tela ao estado de
        "ninguém apareceu ainda", que é degradação, não quebra.
        """
        processo = self._processo
        if processo is None or processo.stdout is None:
            return
        try:
            for linha in processo.stdout:
                candidato = ler_candidato(linha)
                if candidato is None:
                    continue
                with self._tranca:
                    if candidato.endereco in self._vistos:
                        continue
                    self._vistos.add(candidato.endereco)
                    self._achados.append(candidato)
                logger.info(
                    "pareamento_candidato",
                    endereco=candidato.mascara,
                    controle=candidato.e_controle,
                )
        except Exception:
            return

    @property
    def aberta(self) -> bool:
        """A varredura ainda está de pé AGORA?"""
        if self._dono is not None:
            return (
                self._fim is not None and not self._fechada and time.monotonic() < self._fim
            )
        processo = self._processo
        return processo is not None and processo.poll() is None

    def candidatos(self) -> tuple[Candidato, ...]:
        """O que já apareceu nesta volta. Seguro a qualquer momento."""
        self._colher()
        with self._tranca:
            return tuple(self._achados)

    def esperar(self, teto: float | None = None) -> None:
        """Espera a janela fechar sozinha. **Nunca chame isto no tique.**"""
        if self._dono is not None:
            if self._fim is not None:
                resta = self._fim - time.monotonic()
                time.sleep(max(0.0, resta if teto is None else min(resta, teto)))
            self.fechar()
            return
        processo = self._processo
        if processo is None:
            return
        limite = self.segundos + 15 if teto is None else teto
        try:
            processo.wait(timeout=limite)
        except (subprocess.TimeoutExpired, OSError):
            self.fechar()
        if self._fio is not None:
            self._fio.join(timeout=2.0)

    def fechar(self) -> None:
        """Derruba a varredura agora. Idempotente e silencioso."""
        dono = self._dono
        if dono is not None:
            if self._relogio is not None and self._relogio is not threading.current_thread():
                self._relogio.cancel()
            # O relógio e quem chama podem fechar juntos: um só para a busca.
            with self._tranca_de_fechar:
                if not self._no_do_adaptador or self._fechada:
                    return
                # Colhe antes de parar: sem a busca, o BlueZ recolhe os
                # aparelhos que ela achou e que ninguém pareou.
                self._colher()
                self._fechada = True
                dono.parar_busca(self._no_do_adaptador, quem=QUEM)
            return
        processo = self._processo
        if processo is None:
            return
        if processo.poll() is None:
            try:
                processo.terminate()
                processo.wait(timeout=3.0)
            except (subprocess.TimeoutExpired, OSError):
                with contextlib.suppress(OSError):
                    processo.kill()
        for cano in (processo.stdout, processo.stderr):
            if cano is not None:
                with contextlib.suppress(OSError, ValueError):
                    cano.close()

    def __enter__(self) -> JanelaDeBusca:
        self.abrir_a_janela()
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()

    # -- o gesto que ela pede -------------------------------------------------

    def parear(self, endereco: str) -> Resultado:
        """Pareia ESTE endereço, e só enquanto a janela estiver aberta.

        A recusa com a janela fechada não é zelo: o BlueZ recolhe os
        dispositivos que a varredura achou quando ela termina, e o ``Pair()``
        cairia num caminho D-Bus que não existe mais. Recusar com a frase certa
        manda a pessoa procurar de novo; deixar tentar entregaria a mensagem do
        BlueZ, que não diz o que fazer.
        """
        alvo = mac_limpo(endereco)
        if alvo is None:
            return Resultado(ESTADO_NAO_DEU, FRASE_NAO_PAREOU)
        mascara = mascarar(alvo)
        if not self.aberta:
            logger.info("pareamento_fora_da_janela", endereco=mascara)
            return Resultado(ESTADO_JANELA_FECHADA, FRASE_JANELA_FECHADA)
        for achado in self.candidatos():
            if achado.endereco == alvo and achado.ja_pareado:
                logger.info("pareamento_ja_estava", endereco=mascara)
                return Resultado(ESTADO_JA_PAREADO, FRASE_JA_PAREADO)
        if self._dono is not None:
            return self._parear_pelo_dono(self._dono, alvo, mascara)
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        try:
            with bluez_dbus.na_trava(QUEM):
                codigo, erro = self._correr(
                    ["sudo", "-n", "--", self.caminho, "parear", self.adaptador, alvo]
                )
        except TravaOcupadaError as ocupada:
            codigo, erro = 1, str(ocupada)
        if codigo == 0:
            logger.info(
                "pareamento_deu", endereco=mascara, adaptador=mascarar(self.adaptador)
            )
            return Resultado(ESTADO_PAREOU, FRASE_PAREOU)
        logger.warning("pareamento_nao_deu", endereco=mascara, motivo=erro[:200])
        return Resultado(ESTADO_NAO_DEU, FRASE_NAO_PAREOU)

    def _parear_pelo_dono(
        self, dono: bluez_dbus.LeitorDoBluez, alvo: str, mascara: str
    ) -> Resultado:
        """O ``Pair`` pela conexão do dono — atendido pelo agente próprio (R5)."""
        no = dono.caminho_do_aparelho(alvo, adaptador=self.adaptador)
        if no is None:
            logger.warning("pareamento_sem_objeto", endereco=mascara)
            return Resultado(ESTADO_NAO_DEU, FRASE_NAO_PAREOU)
        escrita = dono.parear(no, quem=QUEM)
        if escrita.feita:
            logger.info(
                "pareamento_deu",
                endereco=mascara,
                adaptador=mascarar(self.adaptador),
                pelo_dono=True,
            )
            return Resultado(ESTADO_PAREOU, FRASE_PAREOU)
        logger.warning("pareamento_nao_deu", endereco=mascara, motivo=escrita.erro)
        return Resultado(ESTADO_NAO_DEU, FRASE_NAO_PAREOU)


def impedimentos(caminho: str = PONTE_INSTALADA) -> list[str]:
    """Por que o pareamento pelo Hefesto não pode acontecer agora. Vazio = pode.

    Delega à porta que a ``CONEXAO-ZUMBI-01`` já escreveu: ponte instalada,
    ``sudo`` presente e a regra do ``sudoers.d`` no lugar. Escrever a mesma
    sonda de novo aqui deixaria duas verdades sobre a mesma porta, que é o
    defeito que esta casa mais paga.
    """
    return PontePrivilegiada(caminho=caminho).impedimentos()


def procurar(
    adaptador: str,
    segundos: int = SEGUNDOS_DA_JANELA,
    *,
    caminho: str = PONTE_INSTALADA,
    abrir: Abrir | None = None,
    correr: Correr | None = None,
    conferir_a_porta: bool = True,
    dono: bluez_dbus.LeitorDoBluez | None = None,
) -> Resultado:
    """Abre a janela, espera ela fechar e devolve os candidatos.

    **Bloqueia pelos segundos pedidos.** Não existe para o tique: existe para o
    fio que a aba já sabe abrir. Quem quiser mostrar a lista crescendo usa a
    :class:`JanelaDeBusca` direto.

    A porta privilegiada só é conferida quando a janela é a da PONTE: pelo
    dono vivo não há ``sudo`` no caminho.
    """
    janela = JanelaDeBusca(
        adaptador, segundos, caminho=caminho, abrir=abrir, correr=correr, dono=dono
    )
    if conferir_a_porta and not janela.pelo_dono:
        motivos = impedimentos(caminho)
        if motivos:
            logger.info("pareamento_sem_porta", motivos=len(motivos))
            return Resultado(
                ESTADO_SEM_PORTA, FRASE_SEM_PORTA.format(motivos="; ".join(motivos))
            )
    motivo = janela.abrir_a_janela()
    if motivo:
        logger.warning("pareamento_busca_nao_abriu", motivo=motivo)
        return Resultado(ESTADO_NAO_DEU, FRASE_NAO_DEU)
    try:
        janela.esperar()
    finally:
        janela.fechar()
    achados = janela.candidatos()
    if not achados:
        return Resultado(ESTADO_NINGUEM, FRASE_NINGUEM)
    return Resultado(ESTADO_ACHOU, "", achados)


def segundos_ate(fim: float, *, agora: float | None = None) -> int:
    """Quanto falta da janela, em segundos inteiros e nunca negativo.

    Existe para a tela poder contar sem repetir a aritmética em cada aba — e
    com o relógio por argumento, para a régua viajar no tempo sem dormir.
    """
    momento = time.monotonic() if agora is None else agora
    return max(0, int(fim - momento))


__all__ = [
    "CLASSES_MENORES_DE_CONTROLE",
    "CLASSE_MAIOR_PERIFERICO",
    "ESPERA_DO_PAREAR_S",
    "ESTADO_ACHOU",
    "ESTADO_JANELA_FECHADA",
    "ESTADO_JA_PAREADO",
    "ESTADO_NAO_DEU",
    "ESTADO_NINGUEM",
    "ESTADO_PAREOU",
    "ESTADO_SEM_PORTA",
    "FRASE_JANELA_FECHADA",
    "FRASE_JA_PAREADO",
    "FRASE_NAO_DEU",
    "FRASE_NAO_PAREOU",
    "FRASE_NINGUEM",
    "FRASE_PAREOU",
    "FRASE_SEM_PORTA",
    "QUEM",
    "SEGUNDOS_DA_JANELA",
    "SEGUNDOS_MAX",
    "Candidato",
    "JanelaDeBusca",
    "Resultado",
    "e_controle",
    "impedimentos",
    "ler_candidato",
    "procurar",
    "segundos_ate",
]
