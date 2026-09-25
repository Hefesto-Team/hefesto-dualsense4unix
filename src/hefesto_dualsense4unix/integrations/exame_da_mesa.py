"""O exame da mesa — as conferências que respondem "está tudo certo?".

O `scripts/doctor.sh` sabe responder isso desde sempre, em milhares de linhas
de diagnóstico (o número medido está no documento da sprint, que envelhece
sozinho e não obriga esta página a envelhecer junto). O
problema nunca foi a medição: é que ela só existe para quem abre terminal, que
é a minoria de quem usa o produto. Esta é a mesma leitura, num formato que a
aba Conexões mostra na seção Check-up — uma linha por achado, sem teto.

POR QUE UM MÓDULO PYTHON, E NÃO UM `doctor.sh --json`. O doctor NÃO viaja nos
pacotes: o `install.sh:3778-3780` só copia o `storm_watch.sh`, a spec do Fedora
instala `install-host-udev.sh` e `dkms_lib.sh`, e o manifesto Flatpak não o
menciona. Uma aba que dependesse dele nasceria VAZIA para quem instalou por
pacote — que é a maioria futura. O padrão que a casa já usa três vezes é o
inverso: o módulo viaja dentro do wheel e o doctor é que o consome
(`sentinela_do_wrapper.py` ← `scripts/doctor.sh:1673`).

A DISCIPLINA, herdada de `storm_doctor.py:1-9` e válida linha a linha aqui:

- **Somente leitura.** Nenhuma função deste arquivo escreve em lugar nenhum.
- **Sem root, nunca.** Checagem que precisaria de `sudo` devolve
  ``ESTADO_NAO_SEI`` — jamais falha. O `/var/lib/bluetooth` é proibido por
  isso: `check_bt_bonds_persistidos` (`scripts/doctor.sh:3111-3114`) começa
  com `sudo -n true` e desiste sem ele.
- **Cada caminho entra por argumento**, com default igual ao sistema real. É o
  que permite testar com fixture e é o que permite ao retrato das abas montar
  a tela sem fotografar a máquina de quem mantém o projeto.
- **100% stdlib.** O doctor chama este arquivo pelo `python3` do sistema
  (`check_sentinela_wrapper` não usa o `_python_do_produto`), então uma
  dependência de terceiros aqui viraria uma linha muda na conferência.

O QUE ESTE MÓDULO NÃO FAZ, e é deliberado: ele não devolve frase de tela
pronta nem cor. Devolve chave, estado e um "porquê" curto em português —
escrito AQUI, nunca copiado da mensagem do doctor. As mensagens de lá carregam
`sudo` e carregam endereço de rádio (`scripts/doctor.sh:3288` imprime o MAC),
e as duas coisas acabariam num PNG versionado pelo caminho do retrato das abas.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - só para o verificador de tipos
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Leitura, Ordem
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

#: Os quatro estados de uma linha do exame. O quarto não é enfeite: é o que a
#: checagem devolve quando a resposta exigiria root, ou quando a ferramenta de
#: leitura não existe nesta máquina. Sem ele, a única saída honesta para
#: "não deu para conferir" seria mentir de verde ou assustar de vermelho.
ESTADO_CERTO = "certo"
ESTADO_ATENCAO = "atencao"  # (noqa-acento): chave de máquina, ASCII por contrato
ESTADO_PROBLEMA = "problema"
ESTADO_NAO_SEI = "nao_sei"

#: Rótulos como a pessoa os lê na tela, na ORDEM da tela. Moram aqui, e não na
#: seção da aba, porque o `--relatorio` do terminal mostra os mesmos cinco: dois
#: conjuntos de rótulos para a mesma medição divergiriam na primeira edição.
ROTULO_ENERGIA_DO_RADIO = "Economia de energia desligada"
ROTULO_ENERGIA_DAS_PORTAS = "Energia das portas"
ROTULO_PAREAMENTOS = "Pareamentos salvos"
ROTULO_SUPORTE_AO_CONTROLE = "Suporte ao controle"
ROTULO_VIZINHANCA = "Vizinhança das portas"

#: O rótulo de uma linha que NÃO é conferência: é uma ordem de serviço vinda de
#: `integrations/ordens_da_mesa.py`. Um rótulo só para as seis regras, e não um
#: por regra, porque o que a pessoa lê no card é o IMPERATIVO — este texto só
#: aparece no relatório de terminal, onde ele diz de que espécie é a linha.
ROTULO_DA_ORDEM = "Mudança recomendada"

#: E o rótulo da linha que confessa que o catálogo não rodou. Distinto do de
#: cima de propósito: "não recomendei nada" e "não consegui olhar" são
#: afirmações opostas, e colapsá-las é o F7 desta casa.
ROTULO_DAS_ORDENS = "Mudanças recomendadas"

#: A chave da linha de cima. Não é o slug de regra nenhuma — ela existe
#: justamente para o caso em que nenhuma regra chegou a rodar.
CHAVE_DAS_ORDENS = "ordens_da_mesa"

#: O caminho de UM dispositivo Bluetooth no D-Bus, e nada mais fundo.
#:
#: A âncora de fim é o que importa: a árvore do BlueZ pendura filhos sob cada
#: dispositivo (`.../dev_XX/sep1`, os endpoints de áudio), e eles não têm as
#: propriedades `Paired`/`Bonded`. Sem a âncora, cada controle com áudio traria
#: dois "não sei" a reboque e um pareamento inteiro poderia sair como
#: "não deu para conferir". É o mesmo recorte de `_dbus_bt_device_paths`
#: (`scripts/doctor.sh:2610-2612`), que termina o regex em `$`.
_CAMINHO_DE_DISPOSITIVO = re.compile(r"/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+")


@dataclass(frozen=True)
class Item:
    """Uma linha do exame: o que foi conferido e o que se achou.

    ``porque`` é a MEDIÇÃO em uma frase, não a mensagem do doctor. ``cura`` é o
    que a pessoa pode fazer sem terminal e sem senha — ``None`` quando não há
    nada a fazer, que é o caso normal do estado ``certo``.

    ``ordem`` é a ORDEM DE SERVIÇO desta linha, quando ela tem uma
    (`integrations/ordens_da_mesa.Ordem`): o imperativo, as três linhas de
    porquê e o selo de procedência de cada uma. É por este campo que a cura
    deixa de morar só no ``set_tooltip_text`` — a tela desenha um card com o
    que está aqui, e quem não passa o mouse por cima da palavra certa passa a
    descobrir o que fazer.

    O campo é ``None`` nas cinco conferências, e é assim que ele fica: uma
    conferência responde "está certo?" e uma ordem responde "faça isto". Item
    com ordem é card; item sem ordem continua sendo uma linha da tira.
    """

    chave: str
    rotulo: str
    estado: str
    porque: str
    cura: str | None = None
    ordem: Ordem | None = None

    def como_dicionario(self) -> dict[str, object]:
        """Forma JSON — é o que o `doctor.sh` consome (`--censo`).

        A chave ``ordem`` só existe quando há ordem, e a assimetria é
        deliberada: as cinco conferências publicam exatamente os cinco campos
        que publicavam antes, e nenhum consumidor de `--censo` precisa aprender
        um campo novo para continuar lendo o que já lia. Quem quiser a ordem
        pergunta com ``.get("ordem")``.
        """
        forma: dict[str, object] = {
            "chave": self.chave,
            "rotulo": self.rotulo,
            "estado": self.estado,
            "porque": self.porque,
            "cura": self.cura,
        }
        if self.ordem is not None:
            forma["ordem"] = self.ordem.como_dicionario()
        return forma


# ---------------------------------------------------------------------------
# As cinco checagens, uma função pura por linha da tela.
#
# Cada uma traduz a LÓGICA de um check do doctor, nunca a mensagem dele. O
# endereço da origem está no docstring, e é o que permite conferir se as duas
# leituras ainda concordam no dia em que uma delas mudar.
# ---------------------------------------------------------------------------


def _texto_de(caminho: Path) -> str | None:
    """Conteúdo de um arquivo do sistema, ou ``None`` se não deu para ler.

    Ilegível e inexistente colapsam no mesmo ``None`` de propósito: para o
    exame, "não tenho permissão" e "não existe" levam à mesma frase de tela, e
    distinguir os dois exigiria falar de permissão com quem só quer jogar.
    """
    try:
        return caminho.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def energia_do_radio(
    *,
    parametro: Path = Path("/sys/module/btusb/parameters/enable_autosuspend"),
    conf: Path = Path("/etc/modprobe.d/hefesto-btusb-no-autosuspend.conf"),
) -> Item:
    """O rádio dos controles está proibido de dormir? (`doctor.sh:2401-2417`)

    O `btusb` liga o autosuspend do adaptador no probe, por default do módulo;
    o conf do Hefesto corta na raiz e o esperado pós-boot é ``N``.

    O ramo do meio é o que engana: com o conf JÁ instalado e o módulo ainda com
    o valor antigo, a cura está no disco e não está valendo — só vale no
    próximo probe. Verde ali seria dizer que o rádio não dorme enquanto ele
    ainda dorme.
    """
    valor = _texto_de(parametro)
    if valor in ("N", "0"):
        return Item(
            chave="energia_do_radio",
            rotulo=ROTULO_ENERGIA_DO_RADIO,
            estado=ESTADO_CERTO,
            porque="O sistema está proibido de desligar o rádio dos controles.",
        )
    if conf.is_file():
        if not valor:
            return Item(
                chave="energia_do_radio",
                rotulo=ROTULO_ENERGIA_DO_RADIO,
                estado=ESTADO_NAO_SEI,
                porque=(
                    "A regra está no lugar, mas não há adaptador Bluetooth "
                    "ligado agora para conferir."
                ),
            )
        return Item(
            chave="energia_do_radio",
            rotulo=ROTULO_ENERGIA_DO_RADIO,
            estado=ESTADO_ATENCAO,
            porque=(
                "A regra está no lugar, mas o adaptador só a recebe no "
                "próximo encaixe."
            ),
            cura=(
                "Desencaixe e encaixe o adaptador Bluetooth de novo, ou "
                "reinicie o computador."
            ),
        )
    return Item(
        chave="energia_do_radio",
        rotulo=ROTULO_ENERGIA_DO_RADIO,
        estado=ESTADO_ATENCAO,
        porque=(
            "O sistema pode desligar o adaptador para poupar energia, e "
            "o controle cai no meio do jogo."
        ),
        cura="Rode a instalação do Hefesto de novo: a regra entra por padrão.",
    )


def energia_das_portas(
    *, raiz: Path = Path("/sys/bus/usb/devices")
) -> Item:
    """Nenhuma porta USB em economia de energia? (`doctor.sh:2301-2321`)

    Um aparelho USB dormindo é queda na certa, e a regra 81 do Hefesto existe
    para manter todos em ``on``.

    A frase de saída conta QUANTAS portas, nunca QUAIS. O doctor imprime o
    `idVendor` e o nome do produto de cada uma — informação boa no terminal e
    ruim na tela, porque o retrato das abas publica a tela num PNG versionado.
    """
    total = 0
    dormindo = 0
    try:
        portas = sorted(raiz.iterdir())
    except OSError:
        portas = []
    for porta in portas:
        controle = _texto_de(porta / "power" / "control")
        if controle is None or not (porta / "idVendor").exists():
            continue
        total += 1
        if controle == "auto":
            dormindo += 1
    if total == 0:
        return Item(
            chave="energia_das_portas",
            rotulo=ROTULO_ENERGIA_DAS_PORTAS,
            estado=ESTADO_NAO_SEI,
            porque="Este sistema não deixa ler o estado das portas USB.",
        )
    if dormindo == 0:
        return Item(
            chave="energia_das_portas",
            rotulo=ROTULO_ENERGIA_DAS_PORTAS,
            estado=ESTADO_CERTO,
            porque=(
                f"Nenhuma das {total} portas USB está em economia de energia."
            ),
        )
    return Item(
        chave="energia_das_portas",
        rotulo=ROTULO_ENERGIA_DAS_PORTAS,
        estado=ESTADO_ATENCAO,
        porque=(
            f"{dormindo} das {total} portas USB podem dormir, e o que "
            "estiver nelas cai sem aviso."
        ),
        cura="Rode a instalação do Hefesto de novo: a regra entra por padrão.",
    )


def suporte_ao_controle(
    *,
    modulos: Path = Path("/proc/modules"),
    diretorio_do_modulo: Path = Path("/sys/module/hid_playstation"),
) -> Item:
    """O `hid_playstation` está de pé? (`doctor.sh:393-401`)

    Sem ele o daemon funciona, mas a cor da luz e o LED de jogador somem — por
    isso atenção, e nunca problema.

    O doctor pergunta ao `lsmod`; aqui a pergunta vai direto ao
    ``/proc/modules``, que é o arquivo que o `lsmod` lê. Um subprocesso a menos
    numa função que roda a cada entrada na aba.
    """
    texto = _texto_de(modulos)
    if texto is not None:
        for linha in texto.splitlines():
            if linha.startswith("hid_playstation "):
                return Item(
                    chave="suporte_ao_controle",
                    rotulo=ROTULO_SUPORTE_AO_CONTROLE,
                    estado=ESTADO_CERTO,
                    porque="A parte do sistema que fala com o DualSense está carregada.",
                )
    if diretorio_do_modulo.is_dir():
        return Item(
            chave="suporte_ao_controle",
            rotulo=ROTULO_SUPORTE_AO_CONTROLE,
            estado=ESTADO_CERTO,
            porque="A parte do sistema que fala com o DualSense vem embutida neste kernel.",
        )
    return Item(
        chave="suporte_ao_controle",
        rotulo=ROTULO_SUPORTE_AO_CONTROLE,
        estado=ESTADO_ATENCAO,
        porque=(
            "A parte do sistema que fala com o DualSense não está carregada."
        ),
        cura="Reinicie o computador; se continuar, o kernel pode ser antigo demais.",
    )


def pareamentos(
    *, executar: Callable[[Sequence[str]], str | None] | None = None
) -> Item:
    """Algum controle com pareamento pela metade? (`doctor.sh:3274-3292`)

    "Pela metade" é `Paired: yes` com `Bonded: no` — o sistema lembra do
    controle e não guardou a chave, e o resultado é o controle cair logo depois
    de conectar.

    SÓ pelo D-Bus, e a proibição é doutrina, não gosto: a prova de que o vínculo
    está em disco mora em `/var/lib/bluetooth`, que exige root
    (`scripts/doctor.sh:3111-3114`), e a GUI é sudo-zero.

    Duas fontes de `nao_sei`, as duas honestas: sem `busctl` no caminho, nada
    foi medido; e em BlueZ anterior ao 5.65 a propriedade `Bonded` NEM EXISTE
    (`scripts/doctor.sh:3218-3219`) — ausência dela não é "está tudo bem", é
    "esta máquina não sabe responder".

    A frase de saída nunca carrega o endereço do controle. O `fail` do doctor
    carrega (`:3227`), e ele vai para o terminal de quem pediu; esta vai para
    uma tela que o retrato das abas fotografa e versiona.
    """
    # O dono do BlueZ (BLUEZ-UM-DONO-01), importado AQUI e não no topo: este
    # arquivo é 100% stdlib no import, porque o doctor o roda como script.
    from hefesto_dualsense4unix.integrations import bluez_dbus

    leitor = bluez_dbus.dono() if executar is None else bluez_dbus.pelo_executor(executar)
    arvore = leitor.caminhos()
    if arvore is None:
        return Item(
            chave="pareamentos",
            rotulo=ROTULO_PAREAMENTOS,
            estado=ESTADO_NAO_SEI,
            porque="Não deu para perguntar ao Bluetooth do sistema.",
        )
    caminhos = [c for c in arvore if _CAMINHO_DE_DISPOSITIVO.fullmatch(c)]
    if not caminhos:
        return Item(
            chave="pareamentos",
            rotulo=ROTULO_PAREAMENTOS,
            estado=ESTADO_CERTO,
            porque=(
                "Nenhum controle pareado por BT — não há pareamento pela "
                "metade possível."
            ),
        )
    pela_metade = 0
    sem_resposta = 0
    for caminho in caminhos:
        pareado = bluez_dbus.como_booleano(
            leitor.propriedade(caminho, bluez_dbus.APARELHO, "Paired")
        )
        vinculado = bluez_dbus.como_booleano(
            leitor.propriedade(caminho, bluez_dbus.APARELHO, "Bonded")
        )
        if pareado is None or vinculado is None:
            sem_resposta += 1
            continue
        if pareado and not vinculado:
            pela_metade += 1
    if pela_metade:
        return Item(
            chave="pareamentos",
            rotulo=ROTULO_PAREAMENTOS,
            estado=ESTADO_PROBLEMA,
            porque=(
                f"{pela_metade} pareamento(s) pela metade: o controle cai "
                "logo depois de conectar."
            ),
            cura=(
                "No Bluetooth do sistema, remova esse controle e pareie de "
                "novo segurando o botão PS."
            ),
        )
    if sem_resposta == len(caminhos):
        return Item(
            chave="pareamentos",
            rotulo=ROTULO_PAREAMENTOS,
            estado=ESTADO_NAO_SEI,
            porque="O Bluetooth desta máquina não informa se o pareamento está inteiro.",
        )
    return Item(
        chave="pareamentos",
        rotulo=ROTULO_PAREAMENTOS,
        estado=ESTADO_CERTO,
        porque=(
            f"Nenhum dos {len(caminhos)} pareamentos está "
            "pela metade."
        ),
    )


def _vizinhancas_do_sistema() -> Sequence[object]:
    """Os pares de portas coladas, lidos pela seção "A mesa" da mesma aba.

    Import tardio de propósito: o `mesa_de_radio` varre `/sys` inteiro e nada
    disso pode acontecer no import deste arquivo, que o doctor carrega pelo
    `python3` do sistema a cada conferência.
    """
    from hefesto_dualsense4unix.integrations import mesa_de_radio

    return mesa_de_radio.ler_a_mesa().apertadas


def vizinhanca_das_portas(
    *,
    leitura: Callable[[], Sequence[object]] | None = None,
    altura_da_antena: str | None = None,
    linha_de_visada: str | None = None,
) -> Item:
    """Há aparelho encaixado na porta colada à de outro rádio?

    Esta é a única das cinco que NÃO tem origem no doctor: o que existe lá é o
    `suggest_port` (`scripts/doctor.sh:7211`), um modo à parte que sai antes do
    `main` e se declara "diagnóstico NEUTRO". A medição vem da seção "A mesa"
    da mesma aba (`integrations/mesa_de_radio.py:327`), e o contrato é o mínimo
    possível: uma sequência com uma entrada por par colado. Contar é tudo que
    esta linha precisa — os nós de cada par são assunto da seção que sabe
    desenhá-los.

    `altura_da_antena` e `linha_de_visada` são a declaração da seção "A mesa"
    (`utils/maquina.py:MesaDeclarada`), passada por ARGUMENTO — este módulo é
    100% stdlib e read-only por contrato de CONFIG-09, então quem carrega o
    `maquina.json` é sempre quem chama, nunca este arquivo (T3,
    CONFIGURAÇÕES-FECHA-01). Os dois valores só decidem o TEXTO da cura: a cor
    e o estado continuam vindo só da contagem de pares apertados.

    Qualquer falha de leitura vira `nao_sei`, e a tela DIZ que não sabe:
    inventar verde aqui seria afirmar ausência de ruído sem ter olhado, que é
    o defeito que o quarto estado existe para impedir.

    Laranja, nunca vermelho: porta vizinha ruim atrapalha e tem volta — pintar
    de vermelho ensinaria a ver destruição onde há inconveniência.
    """
    ler = leitura if leitura is not None else _vizinhancas_do_sistema
    try:
        apertadas = list(ler())
    except Exception:
        return Item(
            chave="vizinhanca_das_portas",
            rotulo=ROTULO_VIZINHANCA,
            estado=ESTADO_NAO_SEI,
            porque="Não deu para ler onde cada aparelho está encaixado.",
        )
    if not apertadas:
        return Item(
            chave="vizinhanca_das_portas",
            rotulo=ROTULO_VIZINHANCA,
            estado=ESTADO_CERTO,
            porque="Nenhum aparelho encaixado colado a um adaptador Bluetooth.",
        )
    nada_declarado = altura_da_antena is None and linha_de_visada is None
    if nada_declarado:
        cura = (
            "Abra “Rádio e Adaptadores”, logo abaixo: declare a altura da antena e "
            "a linha de visada para o exame explicar o alcance em vez de só "
            "medi-lo, ou mude um dos dois aparelhos para uma porta mais "
            "longe."
        )
    else:
        cura = (
            "Abra “Rádio e Adaptadores”, logo abaixo, e mude um dos dois para uma "
            "porta mais longe."
        )
    return Item(
        chave="vizinhanca_das_portas",
        rotulo=ROTULO_VIZINHANCA,
        estado=ESTADO_ATENCAO,
        porque=(
            f"{len(apertadas)} par(es) em portas coladas: rádio ao lado de "
            "rádio atrapalha o controle."
        ),
        cura=cura,
    )


# ---------------------------------------------------------------------------
# As ordens de serviço — a sexta espécie de linha, e a única que MANDA.
# ---------------------------------------------------------------------------


def leitura_do_sistema() -> Leitura:
    """O que o catálogo de ordens precisa ler, direto do ``/sys``.

    Só as duas varreduras que não dependem de declaração nenhuma: o censo do
    barramento e os nós de entrada. O desenho do gabinete, os apelidos dos
    rádios e as entradas livres pelo NÚMERO dela moram no ``maquina.json``, que
    é pydantic — e este módulo é 100% stdlib porque o `doctor.sh` o carrega pelo
    ``python3`` do sistema. Quem tem a declaração monta a :class:`Leitura`
    inteira e a passa por argumento, do mesmo jeito que já faz com a altura da
    antena.

    Sem a declaração o catálogo continua respondendo — R1, R3 e R5 saem só do
    barramento. O que ele perde é o ENDEREÇO: sem desenho, a ordem manda mover
    para "uma entrada do próprio computador" em vez de "para a entrada 4".

    Import tardio pela mesma razão de :func:`_vizinhancas_do_sistema`: as duas
    varreduras não podem acontecer no import deste arquivo, que o doctor carrega
    a cada conferência.
    """
    from hefesto_dualsense4unix.integrations import ordens_da_mesa
    from hefesto_dualsense4unix.integrations.censo_do_barramento import (
        ler_o_barramento,
    )
    from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
        listar_entradas,
    )

    return ordens_da_mesa.Leitura(
        censo=ler_o_barramento(), entradas=listar_entradas()
    )


def _itens_das_ordens(leitura: Callable[[], Leitura]) -> list[Item]:
    """Uma linha por ordem de serviço achada — e uma linha se não deu para ver.

    A ordem vira ``Item`` em vez de ganhar uma lista paralela por uma razão de
    dono único: o selo do topo sai de :func:`veredito`, que lê ``estado`` de uma
    lista só. Uma segunda lista obrigaria um segundo lugar a decidir a cor do
    topo, que é exatamente como o verde volta a conviver com o vermelho
    (`6c86e295`, 16/08/2026).

    ``chave`` é o slug da regra, que não colide com as cinco chaves da tira —
    há teste que reprova se um dia colidir, porque a colisão seria muda: a tira
    pintaria a linha errada e ninguém veria erro nenhum.

    Falha de leitura vira ``nao_sei``, com rótulo próprio. Calar deixaria "não
    recomendei nada" indistinguível de "não consegui olhar", que é o F7 desta
    casa aplicado à parte da tela que MANDA.
    """
    from hefesto_dualsense4unix.integrations import ordens_da_mesa

    try:
        catalogo = ordens_da_mesa.catalogo(leitura())
    except Exception:
        return [
            Item(
                chave=CHAVE_DAS_ORDENS,
                rotulo=ROTULO_DAS_ORDENS,
                estado=ESTADO_NAO_SEI,
                porque=(
                    "Não deu para conferir como os aparelhos estão encaixados."
                ),
            )
        ]
    return [
        Item(
            chave=ordem.chave,
            rotulo=ROTULO_DA_ORDEM,
            estado=ESTADO_ATENCAO,
            porque=ordem.o_que_eu_vi.texto,
            cura=ordem.acao or None,
            ordem=ordem,
        )
        for ordem in catalogo
    ]


# ---------------------------------------------------------------------------
# O exame inteiro, e o veredito único.
# ---------------------------------------------------------------------------


def exame(
    *,
    parametro_do_radio: Path | None = None,
    conf_do_radio: Path | None = None,
    raiz_usb: Path | None = None,
    modulos: Path | None = None,
    diretorio_do_modulo: Path | None = None,
    executar_busctl: Callable[[Sequence[str]], str | None] | None = None,
    leitura_da_vizinhanca: Callable[[], Sequence[object]] | None = None,
    altura_da_antena: str | None = None,
    linha_de_visada: str | None = None,
    leitura_das_ordens: Callable[[], Leitura] | None = None,
) -> list[Item]:
    """As cinco linhas, na ORDEM DA TELA.

    A ordem é a do desenho aprovado e não a ordem em que as checagens foram
    escritas: quem lê a tela lê de cima para baixo, e trocar a ordem aqui troca
    a tela.

    Todo caminho é ``None`` por default e cai no default da checagem — assim
    esta assinatura não repete cinco caminhos do sistema real, e o retrato das
    abas continua conseguindo injetar uma bancada falsa em UMA chamada.

    `altura_da_antena` e `linha_de_visada` só alimentam
    :func:`vizinhanca_das_portas` — ver o parágrafo sobre CONFIG-09 lá.

    `leitura_das_ordens` É O ÚNICO ARGUMENTO CUJO DEFAULT NÃO É O SISTEMA REAL,
    e a exceção é a proteção da foto. Os cinco caminhos acima apontam para
    arquivos fixos, e uma bancada os substitui um a um; o catálogo de ordens
    varre o barramento INTEIRO, e quem monta uma bancada para os cinco não tem
    como adivinhar que precisa de um sexto substituto. Pior: o
    `test_com_as_raizes_injetadas_nada_do_sistema_real_e_lido` vigia
    ``pathlib``, e as duas varreduras do catálogo usam ``os.listdir`` e
    ``open`` — o portão passaria verde sobre um exame lendo a máquina dela.
    Com o default desligado, quem quer ordens pede: `main()` pede e
    `app/actions/config/secao_exame.py` pede.

    O terceiro nome desta lista era `scripts/gui-captura/retratar_abas.py`,
    citado como quem NÃO pedia — o retratista da JANELA GTK, apagado com ela em
    06/09/2026 (`D-0609-GTK-LEVA-INTEIRA`). O retratista de hoje
    (`interface/olhar.py`) não pede porque não chega aqui: ele fotografa página
    HTML já gravada, sem executar este módulo.
    """
    argumentos_do_radio: dict[str, Path] = {}
    if parametro_do_radio is not None:
        argumentos_do_radio["parametro"] = parametro_do_radio
    if conf_do_radio is not None:
        argumentos_do_radio["conf"] = conf_do_radio
    argumentos_do_suporte: dict[str, Path] = {}
    if modulos is not None:
        argumentos_do_suporte["modulos"] = modulos  # (noqa-acento): nome de argumento
    if diretorio_do_modulo is not None:
        argumentos_do_suporte["diretorio_do_modulo"] = diretorio_do_modulo

    itens = [
        energia_do_radio(**argumentos_do_radio),
        energia_das_portas(**({"raiz": raiz_usb} if raiz_usb is not None else {})),
        pareamentos(executar=executar_busctl),
        suporte_ao_controle(**argumentos_do_suporte),
        vizinhanca_das_portas(
            leitura=leitura_da_vizinhanca,
            altura_da_antena=altura_da_antena,
            linha_de_visada=linha_de_visada,
        ),
    ]
    if leitura_das_ordens is not None:
        itens.extend(_itens_das_ordens(leitura_das_ordens))
    return itens


def veredito(itens: Sequence[Item]) -> str:
    """O selo do topo, derivado — e derivado em UM lugar só.

    Esta função é a resposta escrita ao commit `6c86e295` (16/08/2026), a
    cicatriz que também está em `scripts/doctor.sh:1647-1651`: *"o dano não é
    errar um diagnóstico: é a tela ensinar que verde-e-vermelho juntos são
    normais por aqui, que é como um portão morre de descrédito"*. A casa pagou
    isso duas vezes em agosto. Por isso o selo NÃO é calculado na tela: um
    segundo lugar que decide a cor do topo é a maneira exata de o verde voltar
    a conviver com o vermelho.

    A escada é de gravidade: um problema derruba tudo; sem problema, uma
    atenção manda; sem nenhum dos dois, um `nao_sei` ainda impede o verde —
    porque "está tudo certo" sobre uma linha que não foi medida é a mesma
    mentira, só mais barata de cometer.

    Lista vazia devolve `nao_sei`: nada foi medido, e nada medido não é bom.
    """
    estados = {item.estado for item in itens}
    for grave in (ESTADO_PROBLEMA, ESTADO_ATENCAO, ESTADO_NAO_SEI):
        if grave in estados:
            return grave
    return ESTADO_CERTO if estados else ESTADO_NAO_SEI


def censo(itens: Sequence[Item] | None = None) -> dict[str, object]:
    """O exame inteiro em forma JSON — é o que o `doctor.sh` consome.

    Recebe os itens em vez de repetir a assinatura de `exame()`: quem quiser
    injetar bancada falsa chama `exame(...)` e passa o resultado, e assim uma
    checagem nova não obriga a mexer aqui.

    Sem itens, é o caminho do terminal — e lá o catálogo de ordens ENTRA: quem
    rodou o comando pediu para olhar esta máquina. Com itens, quem chamou já
    decidiu o que entra, inclusive se há ordens.
    """
    linhas = (
        list(exame(leitura_das_ordens=leitura_do_sistema))
        if itens is None
        else list(itens)
    )
    return {
        "itens": [item.como_dicionario() for item in linhas],
        "veredito": veredito(linhas),
    }


# ---------------------------------------------------------------------------
# O ENDEREÇO DO -71 — STORM-USB-01 (20/09/2026).
#
# O QUE FALTAVA, e não era medição: o `kernel-watch` já grava a porta em cada
# linha `[USB-71]` desde que nasceu, e o `check_kernel_watch`
# (`scripts/doctor.sh:3869`) só CONTAVA — *"33 vez(es) nos últimos 7 dias"*, sem
# dizer onde. Quem lê isso não tem o que fazer com o número: -71 é `EPROTO`, e a
# porta é a única coisa que separa "o cabo daquele controle" de "aquele hub".
#
# O que EXISTIA e não bastava: `check_usb_dropout` (`scripts/doctor.sh:7145`)
# correlaciona, mas só sobre `journalctl -b -k` — o BOOT ATUAL. A queda de
# terça-feira não está lá, e é justamente a que a pessoa quer explicar. O
# `kernel-watch` guarda meses; era o log dele que ninguém cruzava com o `/sys`.
#
# AS CINCO FORMAS DA LINHA, medidas no `kernel.log` desta casa (164 eventos,
# 08/08 a 18/09). O parser cobre as cinco, e as três últimas são o arranjo
# DIFÍCIL — um parser que só pegasse `usb 3-4:` daria verde sobre 40% do log:
#
#     usb 3-4.1.3: device descriptor read/all, error -71   -> 3-4.1.3
#     usbhid 3-4.1.3:1.3: can't add hid device: -71        -> 3-4.1.3  (interface)
#     uvcvideo 1-6:1.0: UVC non compliance ... error -71   -> 1-6      (outro driver)
#     usb usb3-port4: unable to enumerate USB device       -> 3-4      (porta do hub-RAIZ)
#     usb 3-1.1-port3: unable to enumerate USB device      -> 3-1.1.3  (porta de hub)
#
# As duas últimas são a mais informativa das cinco: o aparelho NUNCA enumerou,
# então ele não tem endereço próprio — o kernel nomeia a PORTA FÍSICA, e é dela
# que o número do degrau sai. Prova cruzada nesta bancada: `usb usb1-port6` em
# 24/08 e `uvcvideo 1-6:1.0` no MESMO dia, o mesmo aparelho pelos dois nomes.
#
# E A PERGUNTA 1 DA SPRINT — *"é a porta, o cabo ou o hub?"* — a topologia
# responde: um hub que está no caminho de DUAS OU MAIS portas que deram -71 é o
# fator comum, e :func:`storm_por_porta` o nomeia. Uma porta só nunca acusa o
# hub dela: isso seria trocar a causa pelo endereço.
#
# A PALAVRA DELA DE 23/09 — «NOMEAR E RELIGAR» (24/09/2026). O laudo de 20/09
# dizia o caminho do kernel (`3-4.1.3`), e a palavra dela pede três coisas a mais:
#
# 1. **a ENTRADA, com o nome da seção do rádio.** O dono do nome é
#    `integrations/entrada_a_entrada.nome_da_porta` — o que ela deu, «Entrada 3»
#    pelo desenho, ou «Entrada 4.1.3» pelo `devpath` —, e este módulo PERGUNTA a
#    ele (:func:`_nomeador`), nunca compõe a palavra. Sem o pacote ao alcance (o
#    `python3` do sistema, sem pydantic 2), sobra o caminho do kernel, como antes;
# 2. **o CONTROLE**, e a matriz dela: o -71 não é só do cabo. Os adaptadores BT
#    também são USB, e o -71 num deles derruba todos os controles dele — medido
#    no `kernel.log` dela: os 27 eventos em `1-4` de 13/09 são o TP-Link UB500 no
#    laço de reinícios, e não um DualSense. :attr:`Aparelho.papel` diz qual dos
#    dois está na entrada;
# 3. **o que ficou PARADO.** Duas das formas acima são o kernel DESISTINDO, e
#    nelas o controle não volta sozinho: `unable to enumerate USB device` (a
#    entrada fica vazia — a 3-4.4 da mesa dela, no arranque de 24/09) e `can't
#    add hid device` (o controle fica encaixado sem o HID, mudo para o jogo — a
#    3-4.4 de 16/09, 15 s até a queda seguinte). :attr:`PortaDoStorm.parada` junta
#    o desfecho do log com a leitura de AGORA e diz qual das duas ficou.
#
# O RELIGAR NÃO MORA AQUI: este módulo é só leitura. O controle que fica sem o
# HID é religado pelo `scripts/bt_rebind_orphans.sh` (o ramo do cabo): na hora
# do aviso do kernel, pelo kernel-watch e o verbo `religar-orfaos` da ponte
# privilegiada (STORM-USB-02), e no tique do vigia root do Bluetooth; a entrada
# que o kernel largou vazia pede um reset de porta que nenhum caminho root do
# produto tem hoje — está escrito na sprint, em «O que o install precisa».
#
# E O LUGAR NA LINHA (STORM-USB-02). Desde 24/09 o kernel-watch grava, no fim de
# cada linha `[USB-71]`, o lugar da porta no instante do evento. O caminho do
# kernel carrega o número do barramento, que é a ordem de subida dos xHCI
# daquele boot; :func:`_porta_de_hoje` traduz o lugar pelos barramentos da raiz
# lida, e a entrada nomeada é a certa mesmo que a ordem tenha mudado.
# ---------------------------------------------------------------------------

#: A tag que o `storm_watch.sh:classify` põe na linha do storm.
TAG_DO_STORM = "[USB-71]"

#: Onde o kernel lista os nós USB. Mesmo caminho de :func:`energia_das_portas`.
RAIZ_USB = Path("/sys/bus/usb/devices")

#: `bDeviceClass` de hub. Mesmo valor de `integrations/mesa_de_radio._CLASSE_HUB`,
#: repetido e não importado pela mesma razão daquele arquivo: este módulo é
#: carregado pelo `python3` do sistema e não pode arrastar o pacote inteiro.
CLASSE_DE_HUB = "09"

#: O `idVendor` da Sony: só um aparelho dela vira CONTROLE numa frase deste
#: laudo. Mesmo valor de `integrations/entrada_a_entrada._VID_DA_SONY`, repetido
#: pela razão do :data:`CLASSE_DE_HUB`.
VID_DA_SONY = "054c"

#: Os fabricantes de CONTROLE — quem vira «um controle» na frase. O mesmo
#: conjunto de `integrations/mesa_de_radio._VIDS_DE_CONTROLE`, repetido pela
#: razão do :data:`CLASSE_DE_HUB`, e a régua confere os dois. O produto é para
#: qualquer controle no cabo, não só o dela; o RELIGAR é que segue só Sony
#: (:data:`VID_DA_SONY`), porque é o escopo do script de root.
VIDS_DE_CONTROLE = frozenset({"054c", "057e", "045e", "2dc8", "0f0d", "20d6", "28de"})

#: A tripla do adaptador BT (classe, subclasse, protocolo), a mesma que
#: `censo_do_barramento._especie` lê como «Bluetooth». O TP-Link UB500 da mesa
#: dela publica `e0` já no descritor do APARELHO (medido em 24/09); o adaptador
#: composto a publica só na interface 0, e as duas leituras valem.
TRIPLA_DO_ADAPTADOR = ("e0", "01", "01")

#: A classe de interface HID. O DualSense no cabo tem as de áudio (`01`) e a
#: HID (`03`); é a `03` que o -71 da probe deixa sem driver.
CLASSE_HID = "03"

#: Os dois desfechos em que o kernel DESISTE e não tenta de novo sozinho.
DESFECHO_ENTRADA_LARGADA = "entrada_largada"
DESFECHO_SEM_HID = "sem_hid"

#: `usb 3-4-port4: unable to enumerate USB device` — depois do próprio ciclo de
#: energia (`attempt power cycle`, no journal da mesa dela em 24/09) o kernel
#: larga a entrada e não enumera mais nada nela até alguém tirar e pôr.
_ENTRADA_LARGADA = re.compile(r"unable to enumerate usb device", re.IGNORECASE)

#: `usbhid 3-4.4:1.3: can't add hid device: -71` e a linha irmã da probe. O
#: aparelho enumerou, a interface HID ficou sem driver, e o driver não refaz a
#: probe sozinho.
_PROBE_DO_HID = re.compile(
    r"can.t add hid device|probe with driver usbhid failed", re.IGNORECASE
)

#: `<driver> <alvo>: <mensagem>` — a forma de TODA linha do kernel sobre USB.
#: O `\S+?` é preguiçoso de propósito: em `usbhid 3-4.1.3:1.3: can't add…` ele
#: precisa engolir o `:1.3` para achar o `: ` que separa a mensagem.
_MENSAGEM_DO_KERNEL = re.compile(r"^\s*(?P<driver>\S+)\s+(?P<alvo>\S+?):\s")

#: `usb3-port4` — porta do hub-RAIZ do barramento 3. Vira o nó `3-4`.
_PORTA_DE_HUB_RAIZ = re.compile(r"^usb(?P<bus>\d+)-port(?P<degrau>\d+)$")

#: `3-1.1-port3` — porta 3 do hub que está em `3-1.1`. Vira o nó `3-1.1.3`.
_PORTA_DE_HUB = re.compile(r"^(?P<hub>\d+-\d+(?:\.\d+)*)-port(?P<degrau>\d+)$")

#: `3-4.1.3:1.3` — INTERFACE de um nó. O aparelho é o nó, sem o `:1.3`.
_INTERFACE_USB = re.compile(r"^(?P<no>\d+-\d+(?:\.\d+)*):\d+\.\d+$")

#: `3-4.1.3` — o nó do dispositivo, que é o que o `/sys/bus/usb/devices` lista.
_NO_USB = re.compile(r"^\d+-\d+(?:\.\d+)*$")

#: O LUGAR que o kernel-watch grava no fim da linha do -71 desde a STORM-USB-02
#: (` · lugar pci-0000:0c:00.3-usb-0:4.4`): o controlador PCI e a cadeia de
#: portas, lidos do `/sys` NO INSTANTE do evento. É o que separa a entrada de um
#: -71 de outro boot da entrada que o mesmo caminho do kernel nomeia hoje.
_LUGAR_NA_LINHA = re.compile(r"\s·\slugar\s(?P<lugar>pci-\S+)\s*$")


def porta_do_evento(mensagem: str) -> str:
    """A porta USB de uma mensagem do kernel — ``""`` quando não dá para dizer.

    Recebe o que sobra da linha do `kernel-watch` DEPOIS da tag, e devolve o nó
    USB no formato do `/sys/bus/usb/devices` (``3-4.1.3``).

    ``""`` é resposta, não falha: o dia em que o kernel inventar uma sexta
    forma, esta função devolve vazio e :func:`storm_por_porta` CONTA o evento
    como "sem endereço". Descartá-lo em silêncio faria a soma das portas ficar
    menor que o total e ninguém veria — é o F3 desta casa (*ausência é
    resposta*) escrito em código.
    """
    achado = _MENSAGEM_DO_KERNEL.match(mensagem)
    if achado is None:
        return ""
    alvo = achado.group("alvo")
    # A ORDEM IMPORTA: `3-1.1-port3` também casaria com nada depois, mas
    # `usb3-port4` precisa ser testado antes de `_NO_USB` não o reconhecer.
    de_raiz = _PORTA_DE_HUB_RAIZ.match(alvo)
    if de_raiz is not None:
        return f"{de_raiz.group('bus')}-{de_raiz.group('degrau')}"
    de_hub = _PORTA_DE_HUB.match(alvo)
    if de_hub is not None:
        return f"{de_hub.group('hub')}.{de_hub.group('degrau')}"
    interface = _INTERFACE_USB.match(alvo)
    if interface is not None:
        return interface.group("no")
    if _NO_USB.match(alvo) is not None:
        return alvo
    return ""


def cadeia_da_porta(porta: str) -> tuple[str, ...]:
    """Os nós do caminho até a porta, do mais raso ao mais fundo.

    ``"3-4.1.3"`` → ``("3-4", "3-4.1", "3-4.1.3")``. O último é o aparelho; os
    de antes são os hubs por onde o sinal passou.

    Função de texto puro: ela não olha o ``/sys``. É o que permite nomear o
    caminho de uma porta que já não existe — o caso normal de um -71 de três
    dias atrás, em que o aparelho caiu e não voltou.
    """
    if _NO_USB.match(porta) is None:
        return ()
    bus, _, resto = porta.partition("-")
    degraus = resto.split(".")
    caminho: list[str] = [f"{bus}-{degraus[0]}"]
    for degrau in degraus[1:]:
        caminho.append(f"{caminho[-1]}.{degrau}")
    return tuple(caminho)


@dataclass(frozen=True)
class Aparelho:
    """Quem está numa porta USB AGORA — ou a confissão de que não está ninguém.

    ``presente`` distingue as duas ausências que um leitor apressado colapsa:
    "a porta está vazia" (o aparelho caiu, e o -71 é exatamente o motivo) de
    "não consegui ler". As duas viram a mesma frase de tela, mas nenhuma delas
    vira *"não havia aparelho nenhum"* — porque o evento prova que havia.
    """

    porta: str
    presente: bool = False
    vid: str = ""
    pid: str = ""
    nome: str = ""
    e_hub: bool = False
    #: A tripla ``e0/01/01`` no aparelho ou na interface 0 — o adaptador BT.
    e_adaptador: bool = False
    #: Um controle Sony com a interface HID SEM driver, lido agora: o desfecho
    #: da probe que caiu com -71 (``can't add hid device``).
    hid_sem_driver: bool = False
    #: O nome da ENTRADA, perguntado ao dono (:func:`_nomeador`). Vazio quando
    #: o dono não está ao alcance — aí a frase fica com o caminho do kernel.
    nome_da_entrada: str = ""

    @property
    def onde(self) -> str:
        """«Entrada 3 (3-4.1.3)»: o nome da seção do rádio e o caminho do kernel.

        O caminho fica junto, e não é segundo nome: é o que o suporte procura no
        journal, e o que separa duas entradas que ela chamou igual. Quando o
        NOME já é o caminho — o rótulo de reserva que o dono desempata numa
        máquina com dois controladores USB, «Entrada 3-4» (STORM-USB-02) —, o
        parêntese repetiria o que está escrito ao lado, e sai.
        """
        if self.nome_da_entrada and self.nome_da_entrada != self.porta:
            if self.porta in self.nome_da_entrada.split():
                return self.nome_da_entrada
            return f"{self.nome_da_entrada} ({self.porta})"
        return self.porta

    @property
    def e_controle(self) -> bool:
        """Um aparelho de fabricante de controle, encaixado agora."""
        return self.presente and self.vid.lower() in VIDS_DE_CONTROLE

    @property
    def papel(self) -> str:
        """O que ele é para quem joga — o controle ou o adaptador. ``""`` no resto.

        É a MATRIZ dela escrita numa palavra: o -71 do cabo derruba UM controle;
        o do adaptador derruba todos os que estão nele.
        """
        if self.e_controle:
            return "um controle, pelo USB"
        if self.presente and self.e_adaptador:
            return "um adaptador BT: quando ele cai, caem todos os controles dele"
        return ""

    @property
    def identidade(self) -> str:
        """Como o aparelho se chama numa frase — no tempo verbal do PRESENTE.

        **Esta leitura é de AGORA, e a frase tem de dizer isso.** O -71 pode ser
        de seis dias atrás; o ``/sys`` só sabe quem está encaixado neste
        instante. Escrever *"o TP-Link deu -71"* seria a mesma classe de defeito
        que ela pegou em 03/09 e que o
        `tests/unit/test_o_doctor_diz_quando_foi.py` cobra: um passado contado
        no presente. Quem monta a frase põe o "AGORA" na frente
        (:attr:`PortaDoStorm.porque`), e a ausência é dita como ausência.
        """
        if not self.presente:
            # A FRASE SERVE ÀS DUAS POSIÇÕES — a porta do evento e os hubs do
            # caminho. Dizer aqui "o aparelho que deu -71 não voltou" seria
            # certo para a primeira e FALSO para a segunda: o hub intermediário
            # não deu -71 nenhum, ele só estava no meio.
            return "nada encaixado — e o /sys não guarda quem já esteve aqui"
        nome = self.nome or "aparelho que não publica nome"
        if self.vid and self.pid:
            return f"{nome} ({self.vid}:{self.pid})"
        return nome

    def como_dicionario(self) -> dict[str, object]:
        return {
            "porta": self.porta,
            "presente": self.presente,
            "vid": self.vid,
            "pid": self.pid,
            "nome": self.nome,
            "e_hub": self.e_hub,
            "e_adaptador": self.e_adaptador,
            "hid_sem_driver": self.hid_sem_driver,
            "nome_da_entrada": self.nome_da_entrada,
            "onde": self.onde,
            "papel": self.papel,
            "identidade": self.identidade,
        }


def _interfaces_da_porta(porta: str, raiz_usb: Path) -> list[Path]:
    """As interfaces do nó (``3-4.4:1.0``, ``3-4.4:1.3``…), em ordem. Somente leitura.

    O prefixo é ``f"{porta}:"`` e é exato: ``3-4:*`` não casa ``3-4.1:1.0``.
    """
    try:
        return sorted(raiz_usb.glob(f"{porta}:*"))
    except OSError:
        return []


def _tripla(no: Path, prefixo: str) -> tuple[str, str, str]:
    """``(classe, subclasse, protocolo)`` de um nó ou interface, em minúsculas."""
    classe, subclasse, protocolo = (
        (_texto_de(no / f"{prefixo}{campo}") or "").lower()
        for campo in ("Class", "SubClass", "Protocol")
    )
    return classe, subclasse, protocolo


def _e_adaptador(no: Path, interfaces: Sequence[Path]) -> bool:
    """A tripla do adaptador BT no descritor do aparelho OU na interface 0."""
    if _tripla(no, "bDevice") == TRIPLA_DO_ADAPTADOR:
        return True
    zero = [i for i in interfaces if i.name.endswith(".0")]
    return bool(zero) and _tripla(zero[0], "bInterface") == TRIPLA_DO_ADAPTADOR


def _hid_sem_driver(interfaces: Sequence[Path]) -> bool:
    """Alguma interface HID sem driver, e que ninguém desligou de propósito?

    ``authorized`` em ``0`` é escolha de alguém (a regra 75 faz isso com o áudio
    do DualSense), e não é o -71: essa interface não entra na conta.
    """
    for interface in interfaces:
        if (_texto_de(interface / "bInterfaceClass") or "").lower() != CLASSE_HID:
            continue
        if (_texto_de(interface / "authorized") or "1") == "0":
            continue
        try:
            if not (interface / "driver").exists():
                return True
        except OSError:
            continue
    return False


def aparelho_da_porta(porta: str, *, raiz_usb: Path = RAIZ_USB) -> Aparelho:
    """Lê no ``/sys`` quem está encaixado nesta porta. Somente leitura.

    Porta ausente devolve ``presente=False`` e os campos vazios — e isso É a
    resposta para a maioria dos -71 antigos, porque a porta que derrubou o
    aparelho costuma ser a que ficou vazia.

    Uma porta que EXISTE mas não deixa ler o ``idVendor`` continua
    ``presente=True``, com identidade degradada. O contrário — chamar de vazia
    o que só é ilegível — seria inventar um fato sobre a mesa de quem lê.
    """
    no = raiz_usb / porta
    try:
        presente = no.is_dir()
    except OSError:
        presente = False
    if not presente:
        return Aparelho(porta=porta)
    vid = _texto_de(no / "idVendor") or ""
    interfaces = _interfaces_da_porta(porta, raiz_usb)
    return Aparelho(
        porta=porta,
        presente=True,
        vid=vid,
        pid=(_texto_de(no / "idProduct") or ""),
        nome=(_texto_de(no / "product") or ""),
        e_hub=(_texto_de(no / "bDeviceClass") or "") == CLASSE_DE_HUB,
        e_adaptador=_e_adaptador(no, interfaces),
        hid_sem_driver=(
            vid.lower() == VID_DA_SONY and _hid_sem_driver(interfaces)
        ),
    )


@dataclass(frozen=True)
class PortaDoStorm:
    """Uma entrada que deu -71 na janela: quantos, quando, o que há nela e o que parou."""

    porta: str
    quantos: int
    ultimo: str
    aparelho: Aparelho
    hubs: tuple[Aparelho, ...] = ()
    #: O desfecho do evento MAIS NOVO desta entrada no log — um dos
    #: ``DESFECHO_*``, ou ``""`` quando o kernel seguiu tentando.
    desfecho: str = ""

    @property
    def parada(self) -> str:
        """O que ficou parado NESTA entrada, lido AGORA — ``""`` quando nada ficou.

        Junta os dois tempos, e cada um diz a sua parte: o log diz COMO o kernel
        desistiu; o ``/sys`` diz se continua assim. Uma entrada vazia sem a
        desistência no log não entra aqui: o aparelho pode ter saído pela mão
        dela, e dizer "parou" sobre isso seria inventar a queda.
        """
        if self.aparelho.hid_sem_driver:
            return "o controle está nela sem o HID, e o jogo não o vê"
        if self.desfecho == DESFECHO_ENTRADA_LARGADA and not self.aparelho.presente:
            return "o kernel desistiu dela no -71, e ela segue vazia"
        return ""

    @property
    def porque(self) -> str:
        """A MEDIÇÃO em uma frase — o mesmo contrato do ``porque`` de `Item`.

        DOIS TEMPOS VERBAIS NUMA LINHA SÓ, e eles não se misturam: a contagem e
        a data são do PASSADO (saem do log); quem está na entrada é do PRESENTE
        (sai do ``/sys`` neste instante). O "AGORA" existe para que ninguém leia
        *"o TP-Link deu -71 vinte e sete vezes"* — o que a medição sustenta é
        *"esta entrada deu -71 vinte e sete vezes, e hoje há um TP-Link nela"*.
        """
        quando = f"{self.ultimo[8:10]}/{self.ultimo[5:7]}" if self.ultimo else "?"
        eventos = "1 evento" if self.quantos == 1 else f"{self.quantos} eventos"
        if self.hubs:
            caminho = ", depois ".join(
                f"{hub.onde}: {hub.identidade}" for hub in self.hubs
            )
            quantos_hubs = "1 hub" if len(self.hubs) == 1 else f"{len(self.hubs)} hubs"
            onde = f"atrás de {quantos_hubs} — {caminho}"
        else:
            onde = "direto numa entrada do próprio computador, sem hub no caminho"
        papel = f" — {self.aparelho.papel}" if self.aparelho.papel else ""
        return (
            f"{self.aparelho.onde} — {eventos}, o último em {quando}; nela "
            f"AGORA: {self.aparelho.identidade}{papel}; {onde}"
        )

    def como_dicionario(self) -> dict[str, object]:
        return {
            "porta": self.porta,
            "entrada": self.aparelho.onde,
            "quantos": self.quantos,
            "ultimo": self.ultimo,  # (noqa-acento): chave de máquina, ASCII por contrato
            "desfecho": self.desfecho,
            "parada": self.parada,
            "aparelho": self.aparelho.como_dicionario(),
            "hubs": [hub.como_dicionario() for hub in self.hubs],
            "porque": self.porque,
        }


@dataclass(frozen=True)
class HubEmComum:
    """Um hub no caminho de DUAS OU MAIS entradas que deram -71 na janela."""

    hub: Aparelho
    portas: tuple[str, ...]
    #: As entradas de baixo com o nome do dono, na ordem de ``portas``.
    entradas: tuple[str, ...] = ()

    @property
    def porque(self) -> str:
        abaixo = self.entradas or self.portas
        return (
            f"o hub em {self.hub.onde} está no caminho de "
            f"{len(self.portas)} entradas que deram -71 "
            f"({', '.join(abaixo)}) — é o fator comum que a topologia "
            f"aponta; nela AGORA: {self.hub.identidade}"
        )

    def como_dicionario(self) -> dict[str, object]:
        return {
            "hub": self.hub.como_dicionario(),
            "portas": list(self.portas),
            "entradas": list(self.entradas),
            "porque": self.porque,
        }


@dataclass(frozen=True)
class LaudoDoStorm:
    """O -71 da janela com endereço — o que o doctor passa a dizer.

    ``sem_endereco`` não é sobra: é a parte do total que este módulo NÃO soube
    endereçar, publicada para que a soma das portas possa ser conferida contra
    o número que o `check_kernel_watch` já imprime. Sem ela, um parser que
    deixasse de reconhecer uma forma do kernel ficaria verde para sempre.
    """

    dias: int = 7
    portas: tuple[PortaDoStorm, ...] = ()
    hubs_em_comum: tuple[HubEmComum, ...] = ()
    sem_endereco: int = 0
    porque_nao: str = ""

    @property
    def total(self) -> int:
        return sum(p.quantos for p in self.portas) + self.sem_endereco

    def como_dicionario(self) -> dict[str, object]:
        return {
            "dias": self.dias,
            "total": self.total,
            "sem_endereco": self.sem_endereco,
            "porque_nao": self.porque_nao,
            "portas": [p.como_dicionario() for p in self.portas],
            "hubs_em_comum": [h.como_dicionario() for h in self.hubs_em_comum],
        }


def _sem_nome(_porta: str) -> str | None:
    """O nomeador de quando o dono do nome não está ao alcance."""
    return None


def _nomeador(
    raiz_usb: Path, *, maquina: MaquinaConfig | None = None
) -> Callable[[str], str | None]:
    """Quem dá o nome a uma entrada — o DONO, `entrada_a_entrada.nome_da_porta`.

    A palavra dela de 23/09: *o nome da entrada é o da seção do rádio, e não se
    inventa outro*. Por isso este módulo não compõe «Entrada N»: pergunta.

    OS BARRAMENTOS SÃO OS DA RAIZ LIDA, nunca os do ``/sys`` de quem roda — é a
    mesma regra do ``--raiz-usb``: com o retrato de OUTRA máquina, traduzir o
    caminho pelos controladores desta daria o lugar errado. E o ``maquina.json``
    é DESTA máquina: com uma raiz que não é a do sistema, os nomes que ela deu
    não valem, e sobra o que o desenho dá a qualquer um («Entrada 4.1.3»).

    Nunca levanta. O import falha no ``python3`` do sistema (o dono usa
    pydantic 2), e aí a frase fica com o caminho do kernel, como antes de 24/09.
    """
    try:
        from hefesto_dualsense4unix.integrations.entrada_a_entrada import nome_da_porta
        from hefesto_dualsense4unix.integrations.mesa_de_radio import (
            controladores_dos_barramentos,
        )
        from hefesto_dualsense4unix.utils.maquina import (
            MaquinaConfig as _Maquina,
        )
        from hefesto_dualsense4unix.utils.maquina import carregar_maquina
    except Exception:  # qualquer falha de import é "sem o dono"
        return _sem_nome
    try:
        barramentos = controladores_dos_barramentos(raiz_usb=str(raiz_usb))
        if maquina is None:
            maquina = carregar_maquina() if raiz_usb == RAIZ_USB else _Maquina()
    except Exception:  # a leitura do nome não derruba o laudo
        return _sem_nome

    def nomear(porta: str) -> str | None:
        try:
            return nome_da_porta(porta, maquina=maquina, controladores=barramentos)
        except Exception:  # idem: o nome nunca derruba o laudo
            return None

    return nomear


def _barramentos_da_raiz(raiz_usb: Path) -> dict[int, str]:
    """``{busnum: controlador PCI}`` da raiz lida — ``{}`` quando não se sabe.

    A mesma leitura do :func:`_nomeador`, e pela mesma razão os barramentos são
    os da RAIZ, nunca os de quem roda. Nunca levanta: sem o dono ao alcance (o
    ``python3`` do sistema), o laudo segue com o caminho do log, como antes.
    """
    try:
        from hefesto_dualsense4unix.integrations.mesa_de_radio import (
            controladores_dos_barramentos,
        )

        return dict(controladores_dos_barramentos(raiz_usb=str(raiz_usb)))
    except Exception:  # sem o dono, "não sei" — nunca derruba o laudo
        return {}


def _porta_de_hoje(
    porta: str, lugar: str, barramentos: dict[int, str], raiz_usb: Path
) -> str:
    """O caminho de HOJE da entrada em que o -71 aconteceu — STORM-USB-02.

    O caminho do kernel (``3-4.4``) carrega o número do barramento, e o número
    é a ORDEM em que os controladores xHCI subiram naquele boot. Nos 12 boots
    medidos na mesa dela a ordem não mudou; num computador em que mude, o
    caminho de um -71 de ontem nomeia OUTRA entrada hoje. O ``lugar`` que o
    kernel-watch grava na linha (o controlador PCI e a cadeia de portas) é o
    que diz qual é a certa, e esta função o traduz pelos barramentos da raiz.

    Vale o caminho do log quando a linha não tem lugar (o log de antes de
    24/09), quando não há barramentos lidos, quando a ordem não mudou (o caso
    comum: o mesmo resultado de antes) e quando o controlador daquele boot não
    está mais na máquina — aí não há entrada de hoje para apontar. Dos dois
    lados de uma entrada USB 3 (o 2.0 e o 3.x têm o mesmo lugar), fica o que
    tem aparelho agora; sem nenhum, o 2.0, onde o DualSense e os adaptadores
    enumeram.
    """
    if not lugar or not barramentos:
        return porta
    try:
        from hefesto_dualsense4unix.utils.lugar import (
            caminhos_do_lugar,
            lugar_do_caminho,
        )
    except Exception:  # sem o dono da grafia, o caminho do log
        return porta
    if lugar_do_caminho(porta, barramentos) == lugar:
        return porta
    candidatos = caminhos_do_lugar(lugar, barramentos)
    if not candidatos:
        return porta
    presentes = []
    for candidato in candidatos:
        try:
            if (raiz_usb / candidato).is_dir():
                presentes.append(candidato)
        except OSError:
            continue
    return (presentes or list(candidatos))[0]


def _desfecho(mensagem: str) -> str:
    """O kernel desistiu nesta linha? Um dos ``DESFECHO_*``, ou ``""``."""
    if _ENTRADA_LARGADA.search(mensagem):
        return DESFECHO_ENTRADA_LARGADA
    if _PROBE_DO_HID.search(mensagem):
        return DESFECHO_SEM_HID
    return ""


def storm_por_porta(
    *,
    linhas: Sequence[str] | None = None,
    log: Path | None = None,
    dias: int = 7,
    hoje: datetime.date | None = None,
    raiz_usb: Path = RAIZ_USB,
    nomear: Callable[[str], str | None] | None = None,
) -> LaudoDoStorm:
    """Cada -71 da janela com a ENTRADA e o CONTROLE — a entrega da STORM-USB-01.

    A janela é a mesma do `check_kernel_watch` e pelo mesmo cálculo: data ISO
    comparada como TEXTO contra ``hoje - dias``, sem aritmética por linha. Se
    as duas divergirem, o doctor contaria 33 e endereçaria 31, e a diferença
    apareceria em ``sem_endereco`` — que é onde ela tem de aparecer.

    ``linhas`` existe para a régua; ``log`` é o caminho real. Sem nenhum dos
    dois e sem o arquivo, ``porque_nao`` diz por que não houve medição — nunca
    uma lista vazia, que se leria como "nenhum -71".

    ``nomear`` dá o nome de cada entrada; sem ele, pergunta-se ao dono
    (:func:`_nomeador`) com os barramentos da ``raiz_usb``.
    """
    if linhas is None:
        if log is None:
            return LaudoDoStorm(dias=dias, porque_nao="nenhum log do kernel-watch informado")
        try:
            linhas = log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return LaudoDoStorm(
                dias=dias,
                porque_nao=f"não deu para ler {log}",
            )
    corte = ((hoje or datetime.date.today()) - datetime.timedelta(days=dias)).isoformat()

    quantos: dict[str, int] = {}
    ultimo: dict[str, str] = {}
    #: O carimbo inteiro do evento mais novo de cada entrada, e o desfecho dele.
    #: ``>=`` de propósito: o kernel escreve a desistência no MESMO segundo das
    #: tentativas (`not accepting address` e `unable to enumerate`, medido em
    #: 24/09), e a ordem do log é a ordem em que ele escreveu.
    carimbo: dict[str, str] = {}
    desfecho: dict[str, str] = {}
    sem_endereco = 0
    #: Os barramentos da raiz, lidos UMA vez e só se alguma linha tiver lugar.
    barramentos: dict[int, str] | None = None
    for linha in linhas:
        if TAG_DO_STORM not in linha:
            continue
        data = linha[:10]
        if len(data) < 10 or data < corte:
            continue
        _, _, mensagem = linha.partition(TAG_DO_STORM)
        # O lugar que o kernel-watch grava no fim da linha (STORM-USB-02) sai da
        # mensagem antes de ela ser lida: ela é a do kernel, e só ela.
        lugar = ""
        casou = _LUGAR_NA_LINHA.search(mensagem)
        if casou is not None:
            lugar = casou.group("lugar")
            mensagem = mensagem[: casou.start()]
        porta = porta_do_evento(mensagem.strip())
        if not porta:
            sem_endereco += 1
            continue
        if lugar:
            if barramentos is None:
                barramentos = _barramentos_da_raiz(raiz_usb)
            porta = _porta_de_hoje(porta, lugar, barramentos, raiz_usb)
        quantos[porta] = quantos.get(porta, 0) + 1
        if data > ultimo.get(porta, ""):
            ultimo[porta] = data
        instante = linha[:19]
        if instante >= carimbo.get(porta, ""):
            carimbo[porta] = instante
            desfecho[porta] = _desfecho(mensagem)

    if nomear is None:
        nomear = _nomeador(raiz_usb) if quantos else _sem_nome
    conhecidos: dict[str, Aparelho] = {}

    def _aparelho(porta: str) -> Aparelho:
        if porta not in conhecidos:
            conhecidos[porta] = replace(
                aparelho_da_porta(porta, raiz_usb=raiz_usb),
                nome_da_entrada=nomear(porta) or "",
            )
        return conhecidos[porta]

    portas: list[PortaDoStorm] = []
    for porta in quantos:
        caminho = cadeia_da_porta(porta)
        portas.append(
            PortaDoStorm(
                porta=porta,
                quantos=quantos[porta],
                ultimo=ultimo[porta],
                aparelho=_aparelho(porta),
                hubs=tuple(_aparelho(degrau) for degrau in caminho[:-1]),
                desfecho=desfecho.get(porta, ""),
            )
        )
    # Mais eventos primeiro; empate desempatado pelo nome, para a saída do
    # doctor não dançar entre duas execuções sobre o mesmo log.
    portas.sort(key=lambda p: (-p.quantos, p.porta))

    # O FATOR COMUM. Só conta hub que está no caminho de DUAS portas distintas:
    # com uma só, acusar o hub seria trocar a causa pelo endereço — o aparelho
    # daquela porta explica o evento igualmente bem, e é o suspeito mais barato.
    sob_o_hub: dict[str, list[str]] = {}
    for p in portas:
        for degrau in cadeia_da_porta(p.porta)[:-1]:
            sob_o_hub.setdefault(degrau, []).append(p.porta)
    hubs_em_comum = tuple(
        HubEmComum(
            hub=_aparelho(degrau),
            portas=tuple(sorted(abaixo)),
            entradas=tuple(_aparelho(porta).onde for porta in sorted(abaixo)),
        )
        for degrau, abaixo in sorted(sob_o_hub.items())
        if len(abaixo) >= 2
    )
    return LaudoDoStorm(
        dias=dias,
        portas=tuple(portas),
        hubs_em_comum=hubs_em_comum,
        sem_endereco=sem_endereco,
    )


def log_do_kernel_watch(lar: Path | None = None) -> Path | None:
    """O `kernel.log`, ou o `storm.log` antigo, ou ``None`` se não há nenhum.

    A mesma escada de `scripts/doctor.sh:3881-3882`, portada para que a régua
    não precise adivinhar o caminho — e para que o dia em que o nome mudar
    mexa em um lugar só.
    """
    raiz = (lar or Path.home()) / ".local/state/hefesto-dualsense4unix"
    for nome in ("kernel.log", "storm.log"):
        caminho = raiz / nome
        try:
            if caminho.is_file():
                return caminho
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------
# CLI — o mesmo par `--censo` / `--relatorio` do `sentinela_do_wrapper.py:560`.
# ---------------------------------------------------------------------------

#: Marca de cada estado no relatório de terminal, no vocabulário que o doctor
#: já usa há meses. Aqui NÃO há cor: cor é assunto da tela, e um hex neste
#: arquivo seria a segunda paleta da casa.
_MARCA = {
    ESTADO_CERTO: "[ OK ]",
    ESTADO_ATENCAO: "[WARN]",
    ESTADO_PROBLEMA: "[FAIL]",
    ESTADO_NAO_SEI: "[INFO]",
}


#: O rótulo de cada uma das três linhas de uma ordem, na ordem da tela. Mora
#: aqui, e não só na seção da aba, porque o `--relatorio` do terminal imprime as
#: mesmas três: dois conjuntos de rótulos para a mesma frase divergiriam na
#: primeira edição — a lição de `ROTULO_ENERGIA_DO_RADIO` e companhia.
ROTULOS_DA_ORDEM = ("O que eu vi aqui", "Por que importa", "Ganho esperado")


def _imprimir_relatorio(itens: Sequence[Item]) -> int:
    """Uma linha por conferência, mais o veredito. Devolve o código de saída."""
    for item in itens:
        print(f"{_MARCA.get(item.estado, '[INFO]')} {item.rotulo}: {item.porque}")
        if item.cura:
            print(f"        o que fazer: {item.cura}")
        if item.ordem is not None:
            # As TRÊS, sempre — inclusive a que confessa que o ganho não foi
            # medido. Uma ordem que manda mover sem dizer quanto se ganha é
            # honesta; a mesma com o ganho escondido é palpite com cara de laudo.
            for rotulo, linha in zip(
                ROTULOS_DA_ORDEM, item.ordem.linhas, strict=True
            ):
                fonte = f" ({linha.fonte})" if linha.fonte else ""
                print(f"        {rotulo}: {linha.texto} [{linha.selo}]{fonte}")
    final = veredito(itens)
    print(f"{_MARCA.get(final, '[INFO]')} exame da mesa: {final}")
    return 1 if final == ESTADO_PROBLEMA else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="exame_da_mesa",
        description=(
            "Confere, sem root e sem escrever nada, o que atrapalha um "
            "controle na mesa: energia do rádio, energia das portas, "
            "pareamento pela metade, suporte ao DualSense e a vizinhança das "
            "portas — e manda as mudanças que valem a pena, com de onde sai "
            "cada afirmação. Sem argumentos, --relatorio."
        ),
    )
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument(
        "--relatorio", action="store_true", help="relatório legível (default)"
    )
    grupo.add_argument("--censo", action="store_true", help="o exame em JSON")
    # STORM-USB-01: um modo À PARTE, e não uma sexta linha do exame. O exame é
    # o espelho da seção Check-up da aba Conexões, e acrescentar linha lá muda
    # a TELA — que só fecha com o olho dela. O endereço do -71 é leitura de
    # terminal, então entra por onde o terminal pergunta.
    grupo.add_argument(
        "--storm-usb",
        action="store_true",
        help="o -71 dos últimos dias com a porta, o aparelho e o hub, em JSON",
    )
    parser.add_argument(
        "--log", help="o kernel.log a ler (default: o do kernel-watch desta conta)"
    )
    parser.add_argument(
        "--dias", type=int, default=7, help="a janela do --storm-usb, em dias (7)"
    )
    parser.add_argument(
        "--raiz-usb",
        default=str(RAIZ_USB),
        help=(
            "onde o /sys lista os nós USB. Trocá-lo permite endereçar o -71 "
            "contra um retrato de /sys de OUTRA máquina — é por aqui que a "
            "régua injeta uma bancada e o suporte lê a topologia de quem pediu "
            "ajuda, sem ter a máquina na mão"
        ),
    )
    args = parser.parse_args(argv)

    if args.storm_usb:
        caminho = Path(args.log) if args.log else log_do_kernel_watch()
        laudo = storm_por_porta(
            log=caminho, dias=args.dias, raiz_usb=Path(args.raiz_usb)
        )
        print(json.dumps(laudo.como_dicionario(), ensure_ascii=False))
        return 0
    if args.censo:
        print(json.dumps(censo(), ensure_ascii=False))
        return 0
    return _imprimir_relatorio(exame(leitura_das_ordens=leitura_do_sistema))


if __name__ == "__main__":  # pragma: no cover - entrypoint do doctor
    sys.exit(main())
