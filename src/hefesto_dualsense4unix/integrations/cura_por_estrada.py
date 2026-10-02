"""A cura por estrada — o ambiente entra nos outros lançadores. §5.3, 09/09/2026.

**O QUE ESTA CURA É, em uma frase:** o mesmo ambiente que o atalho de
inicialização entrega a um jogo da Steam, entregue a um jogo de OUTRO lançador
pela estrada que aquele lançador tem.

O ATALHO DA STEAM NÃO ALCANÇA NINGUÉM MAIS, e a razão é dura
--------------------------------------------------------------

`assets/hefesto-launch.sh` é ambiente e só ambiente: lê o `SteamAppId`, abre
`~/.local/state/hefesto-dualsense4unix/launch_env/steam_app_<id>.env` e exporta
o que estiver lá. **Sem `SteamAppId` ele não faz nada** — e nenhum jogo do
Heroic, do Lutris, do RetroArch, do Dolphin ou do mGBA tem um.

Então «chegar» a um jogo de outro lançador é entregar as MESMAS variáveis por
outra estrada. A conta é a mesma (`daemon/launch_env.py` já a fez e já a
escreveu no disco); o que muda é o arquivo em que ela é escrita.

AS DUAS ESTRADAS, e por que são duas
-------------------------------------

======================  ====================================================
`heroic`                `…/config/heroic/config.json`, em
                        `defaultSettings.enviromentOptions` — a lista de
                        `{key, value}` que o Heroic passa a TODO jogo que ele
                        lança. **Medido no disco dela em 09/09/2026: a chave
                        existe e está vazia.** (A grafia sem o segundo `n` é
                        do Heroic, não um erro de digitação daqui.)
os demais               `<lar>/.local/share/flatpak/overrides/<app-id>`,
                        seção `[Environment]` — o mesmo arquivo, byte a byte
                        no mesmo formato, que `flatpak override --user
                        --env=NOME=VALOR <app-id>` escreve
======================  ====================================================

**O QUE CAIU DA SPRINT, e a razão é medida.** A §4 dela previa o Lutris por
jogo (`system: env:` no `.yml` de cada jogo). Duas coisas derrubaram esse
caminho no dia:

1. **não há dependência de YAML nesta casa** — o `pyproject.toml` não declara
   `pyyaml`, e `censo_dos_lancadores._lutris` já tinha recusado importá-la só
   para ler um nome de arquivo. Escrever YAML à mão num arquivo de configuração
   DELA é o tipo de aposta que esta casa não faz;
2. **o Lutris nunca foi aberto na máquina dela** — medido em 09/09/2026,
   `~/.var/app/net.lutris.Lutris` não existe. Não há um `.yml` de jogo em que
   escrever, e a pasta de configuração inteira ainda não nasceu.

O override do Flatpak alcança o mesmo destino: o Lutris DELA é um flatpak, e o
jogo que ele lança roda dentro da caixa dele, herdando o ambiente. É por
lançador e não por jogo — e por jogo não faria diferença, porque **a conta é a
mesma para todos**: o ambiente vem da ponte, não do título.

**NOTA DE 02/10/2026 — O QUE CADUCOU (A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01).**
A lista de exclusão (21/09, fora da Steam desde 01/10) é o caso em que a conta
deixa de ser a mesma para todos: o jogo excluído do Lutris Flatpak herdava da
caixa o `SDL_GAMECONTROLLER_IGNORE_DEVICES` e o `PROTON_DISABLE_HIDRAW`, com o
Modo Nativo ligado em foco — zero controles. A caixa continua sendo a estrada
da carona; o `system.env` do `.yml` do jogo passou a ser a camada da EXCLUSÃO
(«A CAMADA DO JOGO DO LUTRIS», mais abaixo). O motivo 1 caiu: o PyYAML passou a
dependência de execução (por delegação, a validar por ela), o mesmo leitor do
Lutris, e nenhum YAML se escreve à mão. O motivo 2 continua medido: o Lutris
dela segue sem jogo.

O QUE ESTE MÓDULO NUNCA FAZ
----------------------------

* **nunca inventa o ambiente.** Sem o `default.env` no disco — daemon nunca
  ligado, ou desligado desde sempre — a cura RECUSA dizendo. Escrever um
  `SDL_GAMECONTROLLER_IGNORE_DEVICES` deduzido aqui seria uma segunda conta ao
  lado da do daemon, e a segunda conta envelhece calada;
* **nunca apaga o que é dela.** As duas estradas leem, fundem e regravam: um
  `MANGOHUD=1` que ela pôs no Heroic continua lá depois da cura — e a
  PERMISSÃO do arquivo volta como estava, que é parte do que estava lá (ver
  :func:`_escrever_atomico`);
* **nunca escreve fora da allowlist** (`daemon.launch_env.ENV_ALLOWLIST`) e
  das correções que não dependem de controle (:data:`CORRECOES_DA_CARONA`). O
  arquivo do daemon é lido por um wrapper `sh` que filtra por essa lista
  justamente contra arquivo adulterado; a mesma lista filtra aqui.

O QUE É NOSSO TEM UM DONO, E É ESTE MÓDULO — 25/09/2026
--------------------------------------------------------

O-UNINSTALL-NAO-DEIXA-RASTRO-01. A auditoria da ESQUECER-OS-CONTROLES-01
mediu, num lar de mentira: depois do `uninstall.sh --purge-config`, o
`config.json` do Heroic e o override do Flatpak de cada lançador continuavam
com `SDL_GAMECONTROLLER_IGNORE_DEVICES` e `PROTON_DISABLE_HIDRAW` — os jogos
ficavam sem o DualSense físico e sem o Hefesto para servi-lo.

Quem escreve é quem sabe o que escreveu. A cada escrita, o **registro das
estradas** (`estradas.json`, ao lado do `default.env`, dentro do
`launch_env/` que o daemon materializa) anota, por arquivo: cada chave nossa,
os valores que já pusemos nela, o valor que estava lá ANTES da primeira vez, e
o que o arquivo não tinha (o próprio arquivo, a seção `[Environment]`, a lista
`enviromentOptions`). O desfazer (:func:`desfazer_as_estradas`, que o
`uninstall.sh` roda por `--desfazer`) lê esse registro e tira exatamente isso:

* uma chave nossa sai só se o valor ainda for um dos NOSSOS — se ela o mudou
  depois, ele é dela e fica;
* o valor que ela tinha antes volta; o que não existia volta a não existir;
* o que é dela e nunca foi nosso (`MANGOHUD`, a `[Context]`) não é tocado.

**A MESMA CONTA SERVE A ESCRITA.** Uma chave nossa que saiu do ambiente (o
Modo Nativo não tem `IGNORE` nem `DISABLE_HIDRAW`) sai do arquivo na escrita
seguinte, pela mesma regra — antes ela ficava lá, congelada, e o jogo do
Heroic no Modo Nativo abria sem o controle que o Modo Nativo existe para
mostrar.

**O HEROIC COPIA A LISTA GLOBAL PARA DENTRO DE CADA JOGO** (conferência de
25/09/2026, medido no fonte dele e no disco dela): quando ela muda qualquer
opção de um jogo, o `GamesConfig/<jogo>.json` ganha uma cópia inteira do
`enviromentOptions` global, e dali em diante é ELA que vale para aquele jogo.
O desfazer passa por essas cópias com o registro do `config.json` da mesma
casa (:func:`copias_por_jogo_do_heroic`), e tira delas só o valor nosso. A
ESCRITA não entra nas cópias — um jogo com cópia fica com o ambiente do dia em
que ela foi tirada enquanto o Hefesto está instalado; é dívida aberta, não
desta leva.

**O NOME DO PRODUTO, quando o registro não sabe.** Uma instalação anterior a
este registro escreveu sem anotar. Para ela vale a regra do espaço de nomes: as
variáveis que só o produto usa (:data:`_DO_PRODUTO_SEM_REGISTRO`) são
presumidas nossas; as duas que uma pessoa costuma pôr sozinha
(:data:`PODEM_SER_DELA`) não são. O erro mais barato para quem joga é esse: um
`IGNORE` esquecido deixa o jogo com ZERO controles; um `PROTON_DISABLE_HIDRAW`
que ela mesma tivesse posto já tinha sido sobrescrito pelo produto enquanto ele
estava instalado.

**SÓ BIBLIOTECA PADRÃO NO CAMINHO DO DESFAZER, e é estrutural:** o
`uninstall.sh` o roda depois de a `.venv` sair, com o `python3` do sistema,
como faz com o `proton_pin` e o `camadas_vulkan`. Por isso o import de
`utils/xdg_paths` (que puxa o `platformdirs`) é tardio, e o pacote se acha pelo
caminho deste arquivo quando não está instalado.
"""
from __future__ import annotations

import argparse
import configparser
import contextlib
import copy
import json
import os
import stat
import sys
import tempfile
import threading
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import ModuleType
from typing import cast

try:
    from hefesto_dualsense4unix.integrations import sandbox_dos_lancadores as _caixa
except ImportError:  # pragma: no cover - script avulso do uninstall, sem a .venv
    # `python3 <este arquivo>` põe a pasta das integrações no `sys.path`, e não
    # o `src/`: o pacote se acha pelo caminho deste arquivo. A corrente que o
    # desfazer importa (`sandbox_dos_lancadores`, `censo_dos_lancadores`,
    # `identidade_de_janela`) é só biblioteca padrão.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from hefesto_dualsense4unix.integrations import sandbox_dos_lancadores as _caixa

#: AS DUAS ESTRADAS. O nome é o do ARQUIVO que se escreve, e não o do lançador:
#: quem ganhar uma terceira estrada amanhã (um lançador nativo com config
#: própria) acrescenta um valor aqui, e não um `if` no meio da escrita.
HEROIC_CONFIG = "heroic-config"
FLATPAK_OVERRIDE = "flatpak-override"

#: A CHAVE DO HEROIC, com a grafia DELE. `enviromentOptions` — sem o segundo
#: `n` — é como o Heroic gravou desde sempre, e foi lida assim no `config.json`
#: dela em 09/09/2026. Corrigir a grafia aqui escreveria uma chave que o
#: Heroic não lê: seria a cura silenciosa, que é pior que nenhuma.
CHAVE_DO_HEROIC = "enviromentOptions"

#: A FRASE DA RECUSA SEM AMBIENTE. Ela nomeia o que falta e o que fazer, e não
#: menciona arquivo nenhum: «ambiente», «serviço» e «controle» são as palavras
#: da tela; `default.env` é a língua de dentro.
SEM_AMBIENTE = ("O serviço ainda não publicou o ambiente desta sessão. Ligue o "
                "Hefesto, conecte um controle e tente de novo.")

#: A FRASE DA RECUSA SOBRE UM ARQUIVO QUE NÃO ABRE — e ela existe para o
#: produto NÃO reescrever configuração dela por cima de um arquivo que ele não
#: entendeu. Ver :func:`_ler_heroic`.
ILEGIVEL = ("Não consegui ler o `{arquivo}` deste lançador, e não vou "
            "reescrevê-lo por cima. Abra o lançador uma vez e tente de novo.")

#: AS DUAS QUE UMA PESSOA COSTUMA PÔR SOZINHA — o cache de shader da NVIDIA. Com
#: as :data:`DELA_MANDA`, é a leitura do «limpa?» (`utils/memoria_dos_controles`,
#: a régua confere que são iguais): o valor que ela tinha antes da primeira
#: escrita do Hefesto é guardado e volta no desfazer.
PODEM_SER_DELA: frozenset[str] = frozenset(
    {"__GL_SHADER_DISK_CACHE", "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP"})

#: O QUE UMA VERSÃO SEM REGISTRO ESCREVEU, e o conjunto é HISTÓRICO: são as
#: variáveis da `ENV_ALLOWLIST` em 25/09/2026, o dia em que o registro nasceu,
#: menos as :data:`PODEM_SER_DELA`. Uma variável que a allowlist ganhar depois
#: já nasce anotada no registro e NÃO entra aqui. Ela mora neste módulo, e não é
#: lida do daemon, porque o desfazer roda com o `python3` do sistema, e o
#: `daemon/launch_env` puxa dependência que a `.venv` levou junto.
_DO_PRODUTO_SEM_REGISTRO: frozenset[str] = frozenset({
    "SDL_GAMECONTROLLER_IGNORE_DEVICES",
    "SDL_JOYSTICK_HIDAPI",
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS",
    "PROTON_DISABLE_HIDRAW",
    "SDL_ACCELEROMETER_AS_JOYSTICK",
    "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE",
    "PROTON_ENABLE_MHWILDS_USB_AUDIO",
})

#: AS CORREÇÕES QUE NÃO DEPENDEM DE CONTROLE, e a carona as leva junto com a
#: ponte (AS-CORRECOES-AUTOMATICAS-DESLIGAM-O-XALIA-E-O-FOSSILIZE-01, 02/10/2026).
#: O `proton` (Valve e GE) liga o xalia quando `PROTON_USE_XALIA` não vem
#: (GE-Proton10-34 `proton:2093-2099`, o 11-7 em `:2527-2533`), e nem o Heroic
#: nem o Lutris a escrevem. O lançador da Steam já a entrega (`xalia_fora`, em
#: `assets/hefesto-launch.sh`, com o mesmo valor: a régua confere); fora dela,
#: o jogo do Heroic e o do Lutris abriam com o xalia ligado. Ela não passa pela
#: `ENV_ALLOWLIST`, que é a lista do que o serviço publica por estado dos
#: controles. Nasce anotada no registro: não entra no :data:`_DO_PRODUTO_SEM_REGISTRO`.
CORRECOES_DA_CARONA: tuple[tuple[str, str], ...] = (("PROTON_USE_XALIA", "0"),)

#: AS QUE, POSTAS POR ELA, MANDAM: a regra do lançador da Steam («quem já pôs
#: `PROTON_USE_XALIA` manda»). Um valor que já está no arquivo e não é um dos
#: nossos é dela: a carona não escreve por cima, não o anota como nosso, e o
#: desfazer não o toca (:func:`_as_que_ela_pos`, :func:`_tomar`).
DELA_MANDA: frozenset[str] = frozenset(k for k, _ in CORRECOES_DA_CARONA)

#: Quantos valores nossos o registro lembra por chave. O último é o de agora;
#: os de antes cobrem a escrita que caiu no meio e o arquivo que o «devolver»
#: da ESQUECER-OS-CONTROLES-01 trouxe de volta com um valor nosso mais velho.
_VALORES_LEMBRADOS = 16


def _pasta_do_ambiente(pasta: Path | None) -> Path:
    """A pasta `launch_env` — a pedida, ou a do daemon (import tardio).

    O `utils/xdg_paths` puxa o `platformdirs`, que o `python3` do sistema não
    tem: o desfazer do uninstall sempre diz a pasta, e nunca chega aqui.
    """
    if pasta is not None:
        return pasta
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    return launch_env_dir()


def ambiente_da_ponte(pasta: Path | None = None) -> dict[str, str]:
    """O ambiente que o daemon publicou para ESTA sessão — ou `{}`.

    É o `default.env`: o que o wrapper exportaria para um jogo sem perfil
    próprio, que é exatamente o caso de todo jogo dos outros lançadores (nenhum
    tem `steam_app_<id>`). Ler o do daemon em vez de recalcular é o que impede
    duas contas para a mesma pergunta.

    **NUNCA LEVANTA, e `{}` é resposta:** quem chama trata o vazio como recusa
    (:data:`SEM_AMBIENTE`). Um `{}` escrito no disco dela apagaria o ambiente
    que já estivesse lá, que é o contrário da cura.

    O IMPORT DA ALLOWLIST É TARDIO, e é estrutural: `daemon/launch_env.py` puxa
    o daemon inteiro, e este módulo é lido pelo DESENHO da aba 07 — que o
    gerador `aba07.py` importa rodando como script solto, fora da instalação.
    Um import no topo faria o gerador arrastar o daemon para desenhar um botão.
    A lista continua tendo UM dono; só a hora de perguntar a ele mudou.
    """
    from hefesto_dualsense4unix.daemon.launch_env import ENV_ALLOWLIST

    alvo = _pasta_do_ambiente(pasta) / "default.env"
    try:
        cru = alvo.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    fora: dict[str, str] = {}
    for linha in cru.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        nome, _, valor = linha.partition("=")
        nome = nome.strip()
        if nome in ENV_ALLOWLIST:
            fora[nome] = valor.strip()
    return fora


def ambiente_da_carona(pasta: Path | None = None) -> dict[str, str]:
    """O que a carona leva a cada estrada: a ponte e as :data:`CORRECOES_DA_CARONA`.

    Sem a ponte, `{}`: a carona recusa como antes (:data:`SEM_AMBIENTE`), e a
    correção não sai sozinha para um lançador que o serviço nunca alcançou.
    """
    ponte = ambiente_da_ponte(pasta)
    return {**ponte, **dict(CORRECOES_DA_CARONA)} if ponte else {}


@dataclass(frozen=True)
class Estrada:
    """Por onde o ambiente entra NESTE lançador."""

    cartao: str
    tipo: str
    arquivo: Path
    #: Só nas estradas de override — o `app-id` da caixa que recebe o ambiente.
    app_id: str = ""


@dataclass(frozen=True)
class Plano:
    """O que a cura FARIA, antes de fazer.

    ELE EXISTE SEPARADO DA ESCRITA de propósito: a tela precisa saber se há
    botão a oferecer (`tem_estrada`) sem tocar em disco dela, e a régua precisa
    medir a decisão sem exercitar a escrita.
    """

    cartao: str
    estradas: tuple[Estrada, ...] = ()
    ambiente: dict[str, str] = field(default_factory=dict)
    impedimento: str = ""
    #: O NOME QUE A TELA MOSTRA (*"Heroic (Epic · GOG)"*), e não a chave
    #: interna. **MEDIDO NA TELA VIVA em 09/09/2026:** sem ele a tarja dizia
    #: *"Ajustei o ambiente de heroic"* — a chave do `data-lancador` na frente
    #: dela, que é a língua de dentro num recado de tela.
    nome: str = ""
    #: A pasta `launch_env` de onde o ambiente veio — e onde mora o registro
    #: do que a escrita põe nos arquivos dela. `None` = a do daemon.
    pasta_do_ambiente: Path | None = None

    @property
    def rotulo(self) -> str:
        """O que a TELA chama este cartão. A chave interna é a queda."""
        return self.nome or self.cartao


#: Onde o Flatpak do usuário guarda o override de cada aplicativo — no lar,
#: como o `sandbox_dos_lancadores` lê.
_PASTA_DOS_OVERRIDES = ".local/share/flatpak/overrides"

def _pastas_do_heroic(lar: Path | None) -> tuple[Path, ...]:
    """As casas do Heroic em que a carona escreve: as que o censo lê.

    **A REGRA MORA NO CENSO (02/10/2026,
    O-CENSO-RESPONDE-COMO-O-LANCADOR-RESPONDE-01):** a cópia das duas casas que
    morava aqui (`~/.var/app/…/config/heroic` e `~/.config/heroic`, fixas) não
    seguia o XDG, e com o `XDG_CONFIG_HOME` desviado a carona não achava o
    `config.json` do Heroic nativo; nem a regra do programa instalado, e com
    a sobra do Flatpak ela escrevia na casa que nenhum Heroic lê. O ``lar``
    ``None`` é o de verdade, com o XDG do ambiente
    (`censo_dos_lancadores._Onde`).
    """
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    return censo.pastas_lidas("Heroic", lar)


def _pasta_do_heroic(lar: Path | None) -> Path | None:
    """A primeira casa do Heroic que o censo lê (a do Flatpak, quando são duas)."""
    pastas = _pastas_do_heroic(lar)
    return pastas[0] if pastas else None


def estradas_do_cartao(chave: str, atalhos: tuple[str, ...],
                       lar: Path | None = None,
                       raiz_sistema: Path | None = None) -> tuple[Estrada, ...]:
    """Por onde a cura entra neste cartão. Vazio = não há estrada aqui.

    O HEROIC TEM ESTRADA PRÓPRIA e não ganha override, e a escolha é dele, não
    minha: o Heroic MONTA o ambiente do jogo a partir do
    `enviromentOptions` — escrever nos dois lugares poria a mesma variável em
    duas listas que envelhecem separadas, e a próxima pessoa não saberia qual
    manda.

    A STEAM NÃO ENTRA AQUI. Ela tem o atalho de inicialização, que é a estrada
    dela, e um override por cima seria a segunda entrega do mesmo ambiente.
    """
    if chave == "steam":
        return ()
    if chave == "heroic":
        #: COM OS DOIS HEROIC INSTALADOS, A CARONA ENTRA NOS DOIS (02/10/2026):
        #: cada um lança o jogo pela casa dele.
        return tuple(Estrada(chave, HEROIC_CONFIG, pasta / "config.json")
                     for pasta in _pastas_do_heroic(lar))
    lar = Path.home() if lar is None else lar
    raiz = lar / _PASTA_DOS_OVERRIDES
    #: QUEM SABE QUAIS CAIXAS ESTE CARTÃO TEM é o `sandbox_dos_lancadores` —
    #: a mesma função que o cartão «Flatpak» usa para contar. Duas listas de
    #: `app-id`, uma para contar e outra para escrever, divergiriam no dia em
    #: que um cartão ganhasse um segundo programa dentro — que é exatamente o
    #: que o «Dolphin · mGBA» é.
    return tuple(Estrada(chave, FLATPAK_OVERRIDE, raiz / a, a)
                 for a in _caixa.app_ids_instalados(atalhos, lar, raiz_sistema))


def planejar(chave: str, atalhos: tuple[str, ...], lar: Path | None = None,
             pasta_do_ambiente: Path | None = None,
             raiz_sistema: Path | None = None, nome: str = "") -> Plano:
    """O que a cura faria neste cartão — sem escrever um byte.

    :param nome: o rótulo do cartão, para a frase da tela. Sem ele a frase sai
        com a chave interna, que é a língua de dentro num recado dela.
    """
    estradas = estradas_do_cartao(chave, atalhos, lar, raiz_sistema)
    if not estradas:
        return Plano(chave, (), {}, "não há por onde entrar neste lançador",
                     nome, pasta_do_ambiente)
    ambiente = ambiente_da_carona(pasta_do_ambiente)
    if not ambiente:
        return Plano(chave, estradas, {}, SEM_AMBIENTE, nome, pasta_do_ambiente)
    return Plano(chave, estradas, ambiente, "", nome, pasta_do_ambiente)


def tem_estrada(chave: str, atalhos: tuple[str, ...],
                lar: Path | None = None,
                raiz_sistema: Path | None = None) -> bool:
    """Há botão a oferecer neste cartão? — a pergunta da VIGIA.

    Ela NÃO olha o ambiente de propósito. Um botão que some quando o serviço
    está desligado seria a tela escondendo a cura justamente de quem está
    tentando entender por que o controle não chega; o botão fica, e a recusa
    (:data:`SEM_AMBIENTE`) diz o que ligar.

    **ELA ABRE DISCO**, e por isso quem pergunta é `desenho.medir_no_disco`, na
    thread da vigia — nunca a pintura do tique.

    O `raiz_sistema` VIAJA COM O `lar` desde 09/09/2026: sem ele, uma régua com
    lar de mentira ainda ia ler `/var/lib/flatpak` no disco de verdade, e a
    resposta dela dependia da máquina em que rodasse.
    """
    return bool(estradas_do_cartao(chave, atalhos, lar, raiz_sistema))


def _modo_de_nascimento(pasta: Path) -> int:
    """O modo de um arquivo que NASCE nesta pasta — herdado dela.

    **NÃO SE LÊ O `umask` AQUI, e a razão é de thread:** `os.umask` é a única
    forma de consultá-lo pela biblioteca padrão, e consultar é ESCREVER (põe
    zero e devolve o valor). Esta escrita roda na thread de um gesto, com a
    janela viva ao lado; um arquivo que outra thread abrisse naquela janelinha
    nasceria com a permissão errada.

    A PASTA CARREGA A MESMA INTENÇÃO: `~/.local/share/flatpak/overrides` a
    0755 devolve 0644, e uma pasta fechada a 0700 devolve 0600. É o que o
    `flatpak override` produz nas duas máquinas, sem perguntar nada ao processo.
    """
    try:
        return stat.S_IMODE(pasta.stat().st_mode) & 0o666
    except OSError:  # pragma: no cover - a pasta acabou de ser criada
        return 0o644


def _escrever_atomico(alvo: Path, texto: str) -> None:
    """Grava por arquivo temporário no MESMO diretório, e então renomeia.

    Configuração dela: um `write_text` interrompido no meio deixaria o
    `config.json` do Heroic truncado, e o Heroic abriria sem a biblioteca. O
    temporário vizinho garante que ou o arquivo velho está inteiro, ou o novo
    está.

    **E ELE DEVOLVE O MODO E O DONO DO ARQUIVO DELA — 09/09/2026, e sem isto a
    troca era silenciosa.** `NamedTemporaryFile` nasce **0600** (é o contrato
    dele, contra arquivo temporário bisbilhotado), e `replace()` leva o modo do
    TEMPORÁRIO junto: o `config.json` do Heroic dela, medido a **0644** antes
    da cura, ficava **0600** depois. Este módulo promete *"nunca apaga o que já
    estava lá"*, e a permissão de um arquivo é parte do que estava lá — um
    override a 0600 deixa de ser legível por um serviço que rode com outro
    usuário, e ninguém liga isso ao clique de ontem.

    O DONO VAI JUNTO **quando dá**: um `chown` para o mesmo usuário é sempre
    permitido, e para outro usuário só com privilégio que este produto não tem
    (e não quer). O `OSError` é o caso normal, não a exceção — por isso ele
    passa em silêncio: o arquivo continua inteiro, com o modo certo.
    """
    alvo.parent.mkdir(parents=True, exist_ok=True)
    #: O ANTES SE MEDE ANTES DE ESCREVER, e não depois: `replace()` já terá
    #: destruído o modo original quando alguém pensar em perguntar por ele.
    try:
        antes: os.stat_result | None = alvo.stat()
    except OSError:
        antes = None
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=str(alvo.parent),
                prefix=f".{alvo.name}.", suffix=".hefesto", delete=False) as fh:
            tmp = Path(fh.name)
            fh.write(texto)
            fh.flush()
            os.fsync(fh.fileno())
        if antes is None:
            os.chmod(tmp, _modo_de_nascimento(alvo.parent))
        else:
            os.chmod(tmp, stat.S_IMODE(antes.st_mode))
            with contextlib.suppress(OSError):
                os.chown(tmp, antes.st_uid, antes.st_gid)
        tmp.replace(alvo)
        tmp = None
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink(missing_ok=True)


def _ler_heroic(alvo: Path) -> dict[str, object] | None:
    """O `config.json` do Heroic, `{}` se ele não existe, `None` se ILEGÍVEL.

    **OS TRÊS CASOS SÃO DIFERENTES, e confundir dois deles APAGA a configuração
    dela.** Um arquivo que existe e não abre pode estar truncado por um Heroic
    que morreu no meio de um `write` — e reescrevê-lo com `{}` mais o nosso
    ambiente jogaria fora a biblioteca, o caminho do Wine e tudo o mais. Quem
    não sabe ler não pode escrever: ver :func:`escrever_a_estrada`.
    """
    if not alvo.exists():
        return {}
    try:
        dado = cast("object", json.loads(alvo.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None
    return dado if isinstance(dado, dict) else None


# ── O REGISTRO DAS ESTRADAS: o que é nosso, anotado por quem escreve ───────


@dataclass
class Marca:
    """Uma chave nossa num arquivo dela."""

    #: Os valores que o Hefesto já pôs nela, o de agora por último.
    valores: list[str]
    #: O que estava lá antes da primeira escrita (``None`` = nada). Só as
    #: :data:`PODEM_SER_DELA` guardam um valor aqui: as demais são do produto
    #: (ver o cabeçalho, «o nome do produto»).
    antes: str | None = None


@dataclass
class Entrada:
    """O que o Hefesto pôs num arquivo de lançador."""

    tipo: str
    #: O arquivo não existia antes da primeira escrita.
    nasceu: bool = False
    #: As peças de estrutura que o arquivo não tinha e a escrita criou: a seção
    #: ``Environment`` do override, ou ``defaultSettings``/``enviromentOptions``
    #: do Heroic. Vazias depois do desfazer, elas saem.
    moldura: list[str] = field(default_factory=list)
    chaves: dict[str, Marca] = field(default_factory=dict)


#: Um par ``(chave, valor)`` na ordem em que está no arquivo dela.
Pares = list[tuple[str, str]]


def caminho_do_registro(pasta_do_ambiente: Path | None = None) -> Path:
    """O registro mora AO LADO do `default.env`, dentro do `launch_env/`.

    É a mesma pasta de onde a escrita tira o ambiente, a que o daemon
    materializa a cada transição e que o uninstall apaga — depois de desfazer.
    """
    return _pasta_do_ambiente(pasta_do_ambiente) / "estradas.json"


def _entrada_de(dado: object) -> Entrada | None:
    """Uma entrada lida do disco; torta = ``None`` (o registro nunca levanta)."""
    if not isinstance(dado, dict):
        return None
    tipo = dado.get("tipo")
    if tipo not in (HEROIC_CONFIG, FLATPAK_OVERRIDE):
        return None
    chaves: dict[str, Marca] = {}
    cru = dado.get("chaves")
    for nome, marca in (cru.items() if isinstance(cru, dict) else ()):
        if not isinstance(marca, dict):
            continue
        valores = [str(v) for v in marca.get("valores", []) if isinstance(v, str)]
        if not valores:
            continue
        antes = marca.get("antes")
        chaves[str(nome)] = Marca(valores, antes if isinstance(antes, str) else None)
    moldura = dado.get("moldura")
    return Entrada(
        str(tipo), bool(dado.get("nasceu")),
        [str(x) for x in moldura] if isinstance(moldura, list) else [], chaves)


def ler_registro(pasta_do_ambiente: Path | None = None) -> dict[str, Entrada]:
    """``{arquivo: entrada}``. Ausente ou torto = ``{}`` — NUNCA levanta."""
    try:
        dado = json.loads(caminho_do_registro(pasta_do_ambiente).read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    arquivos = dado.get("arquivos") if isinstance(dado, dict) else None
    fora: dict[str, Entrada] = {}
    for caminho, cru in (arquivos.items() if isinstance(arquivos, dict) else ()):
        entrada = _entrada_de(cru)
        if entrada is not None:
            fora[str(caminho)] = entrada
    return fora


def gravar_registro(registro: dict[str, Entrada],
                    pasta_do_ambiente: Path | None = None) -> None:
    """Grava o registro — e, vazio, o apaga: nada nosso, nada a lembrar."""
    alvo = caminho_do_registro(pasta_do_ambiente)
    if not registro:
        alvo.unlink(missing_ok=True)
        return
    dado = {"forma": 1, "arquivos": {
        caminho: {"tipo": e.tipo, "nasceu": e.nasceu, "moldura": e.moldura,
                  "chaves": {k: {"valores": m.valores, "antes": m.antes}
                             for k, m in sorted(e.chaves.items())}}
        for caminho, e in sorted(registro.items())}}
    _escrever_atomico(alvo, json.dumps(dado, indent=2, ensure_ascii=False) + "\n")


def _entrada_para(alvo: Path, tipo: str, entrada: Entrada | None) -> Entrada:
    """A entrada que a escrita atualiza — nova quando o arquivo não existe.

    Um arquivo que sumiu (ela o apagou) e volta a nascer começa do zero: o
    «antes» da entrada velha falava de um arquivo que não existe mais.
    """
    if not alvo.exists():
        return Entrada(tipo, nasceu=True)
    if entrada is None or entrada.tipo != tipo:
        return Entrada(tipo)
    return copy.deepcopy(entrada)


def _anotar_moldura(entrada: Entrada, *pecas: str) -> None:
    for peca in pecas:
        if peca not in entrada.moldura:
            entrada.moldura.append(peca)


def _por_por_cima(pares: Pares, ambiente: dict[str, str]) -> Pares:
    """As nossas no lugar em que já estavam; as que faltam, no fim, em ordem.

    O QUE JÁ ESTAVA LÁ FICA, na ordem em que estava — um `MANGOHUD=1` dela não
    some porque o Hefesto passou por ali. Uma chave nossa repetida na lista
    dela vira uma só.
    """
    fora: Pares = []
    vistas: set[str] = set()
    for chave, valor in pares:
        if chave not in ambiente:
            fora.append((chave, valor))
        elif chave not in vistas:
            vistas.add(chave)
            fora.append((chave, ambiente[chave]))
    fora += [(k, v) for k, v in sorted(ambiente.items()) if k not in vistas]
    return fora


@dataclass
class _Contas:
    tiradas: list[str] = field(default_factory=list)
    devolvidas: list[str] = field(default_factory=list)
    ficaram: list[str] = field(default_factory=list)


def _devolver_chaves(pares: Pares, chaves: Iterable[str], entrada: Entrada,
                     contas: _Contas) -> Pares:
    """Tira as chaves nossas pedidas — só onde o valor ainda é NOSSO.

    Um valor que ela mudou depois do Hefesto é dela e fica. O valor que estava
    lá antes da primeira escrita volta; o que não existia volta a não existir.
    A chave sai do registro nos dois casos: dali em diante ela é dela.

    **O VALOR DE ANTES VOLTA NO LUGAR EM QUE ESTAVA** (conferência de 25/09): a
    escrita pôs o nosso por cima do dela, na mesma posição
    (:func:`_por_por_cima`), e o desfazer o devolve ali — não no fim da lista.
    """
    for chave in list(chaves):
        marca = entrada.chaves.pop(chave)
        nossos = set(marca.valores)
        if not any(a == chave and b in nossos for a, b in pares):
            #: O valor de antes de uma :data:`DELA_MANDA` nunca foi trocado pelo
            #: Hefesto: é dela desde antes, e não «mudou depois».
            if any(a == chave and not (chave in DELA_MANDA and b == marca.antes)
                   for a, b in pares):
                contas.ficaram.append(chave)
            continue
        #: Um valor que não é nosso na mesma chave é dela, e o de antes não volta
        #: por cima dele.
        devolver = marca.antes is not None and not any(
            a == chave and b not in nossos for a, b in pares)
        novos: Pares = []
        for a, b in pares:
            if a == chave and b in nossos:
                if devolver and marca.antes is not None:
                    novos.append((a, marca.antes))
                    devolver = False
                    contas.devolvidas.append(chave)
                continue
            novos.append((a, b))
        pares = novos
        contas.tiradas.append(chave)
    return pares


def _as_que_ela_pos(pares: Pares, ambiente: dict[str, str],
                    entrada: Entrada) -> frozenset[str]:
    """As :data:`DELA_MANDA` do ambiente que ela já pôs neste arquivo.

    É dela o valor que está no arquivo e não é um dos nossos no registro: o que
    ela pôs antes do Hefesto (sem marca) e o que ela trocou depois.
    """
    dela: set[str] = set()
    for chave in DELA_MANDA & ambiente.keys():
        marca = entrada.chaves.get(chave)
        nossos = set(marca.valores) if marca is not None else set()
        if any(a == chave and b not in nossos for a, b in pares):
            dela.add(chave)
    return frozenset(dela)


def _tomar(pares: Pares, ambiente: dict[str, str], entrada: Entrada) -> Pares:
    """A ESCRITA sobre os pares do arquivo, anotando no registro o que é nosso.

    Uma chave nossa que saiu do ambiente sai do arquivo (o Modo Nativo não tem
    `IGNORE`: um `IGNORE` congelado no Heroic deixava o jogo sem o controle
    que o Modo Nativo existe para mostrar). As de agora entram por cima, menos
    as :data:`DELA_MANDA` que ela já pôs (:func:`_as_que_ela_pos`).

    **A DELA FICA, E A MARCA TAMBÉM.** O registro da lista global do Heroic é o
    das cópias por jogo: com o valor dela na global, a carona ainda põe o nosso
    na cópia que não tem a chave, e o desfazer e a exclusão só o reconhecem pela
    marca da global. Sem a marca, o nosso ficava na cópia depois do uninstall e
    entrava no jogo excluído. O «antes» de uma :data:`DELA_MANDA` é o valor que
    estava no arquivo e só vale enquanto a chave estiver lá: quando o nosso
    entra numa chave vazia, ele volta a ``None``, e o desfazer não devolve um
    valor que ela já tirou.
    """
    dela = _as_que_ela_pos(pares, ambiente, entrada)
    atual = dict(pares)
    pares = _devolver_chaves(
        pares, [k for k in entrada.chaves if k not in ambiente], entrada, _Contas())
    for chave, valor in ambiente.items():
        marca = entrada.chaves.get(chave)
        if marca is None:
            #: A PRIMEIRA VEZ. Só as que podem ser dela guardam o «antes»: as
            #: demais são do produto, e um valor que já estava lá é presumido de
            #: uma versão que escrevia sem registro (ver o cabeçalho).
            antes = atual.get(chave) if chave in PODEM_SER_DELA | DELA_MANDA else None
            entrada.chaves[chave] = Marca([valor], antes)
        elif marca.valores[-1] != valor:
            marca.valores = (
                [v for v in marca.valores if v != valor] + [valor])[-_VALORES_LEMBRADOS:]
        if chave in DELA_MANDA and chave not in atual:
            entrada.chaves[chave].antes = None
    return _por_por_cima(pares, {k: v for k, v in ambiente.items() if k not in dela})


def _desfazer_pares(pares: Pares, entrada: Entrada) -> tuple[Pares, _Contas]:
    """O DESFAZER sobre os pares: as do registro, e as do produto sem registro."""
    contas = _Contas()
    sem_registro = sorted({a for a, _ in pares
                           if a in _DO_PRODUTO_SEM_REGISTRO and a not in entrada.chaves})
    pares = [(a, b) for a, b in pares if a not in sem_registro]
    contas.tiradas += sem_registro
    pares = _devolver_chaves(pares, list(entrada.chaves), entrada, contas)
    return pares, contas


def _pares_da_lista(lista: object) -> Pares:
    """Os pares de uma lista `enviromentOptions` do Heroic (a global ou a de um jogo)."""
    return [(str(x.get("key", "")), str(x.get("value", "")))
            for x in (lista if isinstance(lista, list) else []) if isinstance(x, dict)]


def _pares_do_heroic(raiz: dict[str, object]) -> Pares:
    padroes = raiz.get("defaultSettings")
    return _pares_da_lista(padroes.get(CHAVE_DO_HEROIC) if isinstance(padroes, dict) else None)


def _heroic_fundido(alvo: Path, ambiente: dict[str, str],
                    entrada: Entrada | None = None) -> tuple[str, Entrada]:
    """O `config.json` do Heroic com o ambiente fundido, e o registro dele.

    Não escreve: é a conta. A lista é de `{key, value}`; o resto do arquivo
    (a biblioteca, o caminho do Wine, a língua) passa intacto.
    """
    nova = _entrada_para(alvo, HEROIC_CONFIG, entrada)
    raiz = _ler_heroic(alvo) or {}
    padroes = raiz.get("defaultSettings")
    if not isinstance(padroes, dict):
        padroes = {}
        _anotar_moldura(nova, "defaultSettings", CHAVE_DO_HEROIC)
    elif not isinstance(padroes.get(CHAVE_DO_HEROIC), list):
        _anotar_moldura(nova, CHAVE_DO_HEROIC)
    pares = _tomar(_pares_do_heroic({"defaultSettings": padroes}), ambiente, nova)
    padroes[CHAVE_DO_HEROIC] = [{"key": k, "value": v} for k, v in pares]
    raiz["defaultSettings"] = padroes
    return json.dumps(raiz, indent=2, ensure_ascii=False) + "\n", nova


def _escrever_no_heroic(alvo: Path, ambiente: dict[str, str],
                        entrada: Entrada | None = None) -> Entrada:
    """Funde o ambiente em `defaultSettings.enviromentOptions` e grava.

    O QUE JÁ ESTAVA LÁ FICA: as nossas substituem as de mesmo `key` e as
    demais seguem na ordem em que estavam. Devolve o registro do arquivo.
    """
    texto, nova = _heroic_fundido(alvo, ambiente, entrada)
    _escrever_atomico(alvo, texto)
    return nova


def _render_ini(cfg: configparser.ConfigParser) -> str:
    """O arquivo de override como o Flatpak o escreve — `chave=valor`, sem espaço.

    NÃO SE USA `ConfigParser.write`, e a razão é de FORMATO: ele emite
    `chave = valor`, com espaços, e o arquivo é lido pelo `GKeyFile` do Flatpak.
    Escrever num formato que o dono do arquivo não emite é convidar o dia em que
    ele deixa de ler — num arquivo de configuração dela, e sem aviso.
    """
    partes: list[str] = []
    for secao in cfg.sections():
        partes.append(f"[{secao}]")
        partes += [f"{k}={v}" for k, v in cfg.items(secao)]
        partes.append("")
    return "\n".join(partes).rstrip("\n") + "\n"


def _ler_override(alvo: Path) -> configparser.ConfigParser | None:
    """O override deste aplicativo, vazio se não existe, `None` se ILEGÍVEL.

    A MESMA DISCIPLINA DE :func:`_ler_heroic`, e pela mesma razão: um override
    que existe e não abre pode ter a `[Context]` inteira dela lá dentro, e
    reescrevê-lo só com o nosso `[Environment]` tiraria do aplicativo o acesso
    que ela deu à mão.
    """
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    cfg.optionxform = str  # type: ignore[method-assign,assignment]
    if not alvo.exists():
        return cfg
    try:
        cfg.read_string(alvo.read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error):
        return None
    return cfg


def _repor_secao(cfg: configparser.ConfigParser, secao: str, pares: Pares) -> None:
    """A seção com estes pares, nesta ordem — sem mudar o lugar dela no arquivo."""
    for chave in list(cfg.options(secao)):
        cfg.remove_option(secao, chave)
    for chave, valor in pares:
        cfg.set(secao, chave, valor)


def _override_fundido(alvo: Path, ambiente: dict[str, str],
                      entrada: Entrada | None = None) -> tuple[str, Entrada]:
    """O override com o ambiente em `[Environment]`, e o registro dele. Não escreve."""
    nova = _entrada_para(alvo, FLATPAK_OVERRIDE, entrada)
    cfg = _ler_override(alvo)
    if cfg is None:  # pragma: no cover - `escrever_a_estrada` já recusou antes
        raise RuntimeError(ILEGIVEL.format(arquivo=alvo.name))
    if not cfg.has_section("Environment"):
        cfg.add_section("Environment")
        _anotar_moldura(nova, "Environment")
    pares = _tomar(list(cfg.items("Environment")), ambiente, nova)
    _repor_secao(cfg, "Environment", pares)
    return _render_ini(cfg), nova


def _escrever_no_override(alvo: Path, ambiente: dict[str, str],
                          entrada: Entrada | None = None) -> Entrada:
    """Põe o ambiente em `[Environment]`, preservando todo o resto do arquivo.

    É O MESMO ARQUIVO de `flatpak override --user --env=NOME=VALOR`, e por isso
    ele continua reversível pelo caminho dela: `flatpak override --user --reset`
    apaga o arquivo inteiro, e `--unset-env=NOME` tira uma linha. Devolve o
    registro do arquivo.
    """
    texto, nova = _override_fundido(alvo, ambiente, entrada)
    _escrever_atomico(alvo, texto)
    return nova


def frase_do_feito(plano: Plano) -> str:
    """O recibo que a tela mostra — e ele diz o que mudou, onde e o que fazer.

    **A PALAVRA É A DO GLOSSÁRIO DESTA CASA.** «ambiente» sozinho não diz nada
    a quem clica; o que o `docs/A-LINGUA-DESTA-CASA` já usa para este fato é
    *"faz o jogo enxergar o controle pelo Hefesto"*, na linha do atalho de
    inicialização. É o mesmo fato por outra estrada, e por isso a mesma frase.

    **SEM ARTIGO ANTES DO NOME**, pela razão que a
    `desenho_dos_lancadores.NOVO_PARA_O_CARTAO` já mediu em 08/09/2026: o nome
    vem do cartão — inclusive de um que ELA acrescentou —, e adivinhar o gênero
    de um nome que ainda não existe é palpite na tela dela.

    UMA MONTADORA SÓ, e ela é pública porque a régua a lê. Montar a frase
    dentro da escrita obrigaria a régua a escrever num arquivo para saber o que
    a tela diria.
    """
    n = len(plano.ambiente)
    k = len(plano.estradas)
    quantos = f"os {k} programas " if k > 1 else ""
    cada = " em cada" if k > 1 else ""
    return (f"{plano.rotulo}: ajustei {quantos}para o jogo enxergar o controle "
            f"pelo Hefesto — {n} {'ajuste' if n == 1 else 'ajustes'}{cada}. "
            "Feche e abra o lançador para valer.")


def escrever_a_estrada(plano: Plano) -> str:
    """Escreve o ambiente nas estradas do plano e diz o que escreveu.

    **RECUSA LEVANTANDO**, que é o contrato desta casa para "o produto não
    fez": um retorno mudo viraria piscada verde sobre um arquivo que ninguém
    tocou. A frase da recusa é a que a tela mostra.

    A FRASE DE SUCESSO DIZ O QUE FOI ESCRITO E ONDE — não *"pronto"*. Ela é a
    única prova que ela tem, sem abrir um terminal, de que o clique alcançou
    alguma coisa; e é o que a régua lê para saber que a escrita aconteceu.
    """
    if plano.impedimento:
        raise RuntimeError(plano.impedimento)
    if not plano.estradas:
        raise RuntimeError("não há por onde entrar neste lançador")
    if not plano.ambiente:
        raise RuntimeError(SEM_AMBIENTE)
    #: **NINGUÉM ESCREVE ANTES DE TODOS SEREM LEGÍVEIS.** Um cartão pode ter
    #: DUAS estradas, e recusar no meio do laço deixaria uma escrita e a outra
    #: não, com a tela mostrando só a recusa — o pior dos dois mundos. A
    #: conferência inteira vem primeiro; depois é só escrever.
    for estrada in plano.estradas:
        legivel = (_ler_heroic(estrada.arquivo) if estrada.tipo == HEROIC_CONFIG
                   else _ler_override(estrada.arquivo))
        if legivel is None:
            raise RuntimeError(ILEGIVEL.format(arquivo=estrada.arquivo.name))
    lido = ler_registro(plano.pasta_do_ambiente)
    registro = dict(lido)
    textos: list[tuple[Path, str]] = []
    for estrada in plano.estradas:
        fundir = _heroic_fundido if estrada.tipo == HEROIC_CONFIG else _override_fundido
        texto, entrada = fundir(estrada.arquivo, plano.ambiente,
                                registro.get(str(estrada.arquivo)))
        registro[str(estrada.arquivo)] = entrada
        textos.append((estrada.arquivo, texto))
    #: O REGISTRO VAI ANTES DOS ARQUIVOS, e a ordem é a do lado seguro: uma
    #: escrita que cair no meio deixa o registro dizendo «nosso» sobre um valor
    #: que ainda não chegou — e o desfazer, que só tira valor nosso, não tira
    #: nada que não esteja lá. Na ordem inversa, o valor chegaria sem ninguém
    #: saber de quem é.
    if registro != lido:
        gravar_registro(registro, plano.pasta_do_ambiente)
    for alvo, texto in textos:
        _escrever_atomico(alvo, texto)
    return frase_do_feito(plano)


#: OS CARTÕES QUE TÊM ESTRADA, e os `app-id`/`stem` que os denunciam.
#:
#: **A TABELA NÃO É NOVA — ela é LIDA do censo** (`censo_dos_lancadores._ONDE`),
#: que já a tem por outra razão (achar a pasta de configuração). Uma segunda
#: cópia aqui divergiria no dia em que um lançador trocasse de `app-id`, e o
#: sintoma seria o pior desta casa: a cura escreveria no arquivo de ontem e a
#: tela diria «pronto».
#:
#: A STEAM NÃO ENTRA, e a razão está em `estradas_do_cartao`: ela tem o atalho
#: de inicialização, que é a estrada dela.
def cartoes_com_estrada() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """`[(chave, atalhos)]` dos lançadores que podem receber a cura."""
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import _ONDE

    return tuple(
        (lancador.casefold(), (app_id, subpasta))
        for lancador, (app_id, subpasta) in _ONDE.items())


def curar_todas_as_estradas(
    lar: Path | None = None,
    pasta_do_ambiente: Path | None = None,
    raiz_sistema: Path | None = None,
    exclusao: NaExclusao | None = None,
    espera: float | None = None,
) -> tuple[str, ...]:
    """Escreve o ambiente da ponte em TODA estrada que existir. O que escreveu.

    **POR QUE ESTA FUNÇÃO EXISTE — 21/09/2026, LANCADOR-AGNOSTICO-01.** Ordem
    dela: *"O PROJETO E SUAS FEATURES DEVEM FUNCIONAR INDEPENDENTE DO LANÇADOR
    SER STEAM. QUALQUER OUTRO LANÇADOR O FUNCIONAMENTO SEGUE IGUAL."*

    Este módulo inteiro estava **ÓRFÃO desde 10/09/2026**. Ele nasceu com um
    chamador só — o botão «Consertar» do cartão do lançador —, e a
    LANCADOR-LOCALIZAR-01 tirou o botão. A cura ficou escrita, testada e sem
    ninguém para acioná-la; a dívida ficou declarada no `casa-sabe`, que é
    honesto e não é entrega.

    **O QUE ISSO CUSTAVA, e é a diferença estrutural entre a Steam e o resto:**
    a Steam recebe o ambiente VIVO — o daemon rematerializa o `default.env` a
    cada transição e o `hefesto-launch.sh` o lê no lançamento. Os outros
    lançadores recebiam uma FOTOCÓPIA tirada no dia em que alguém clicou um
    botão que não existe mais. Um ambiente de 10/09 num produto que mudou todo
    dia desde então.

    **A CURA É CARONA, E NÃO BOTÃO**, e é o que a torna simétrica: quem chama é
    o mesmo ponto que já regrava o `default.env` da Steam
    (`daemon/launch_env.materialize_launch_env`). As duas estradas passam a ser
    reescritas pelo mesmo gatilho, com a mesma conta — que é literalmente o
    *"o funcionamento segue igual"* que ela pediu.

    **IDEMPOTENTE E FUNDE, e isso já era verdade antes desta função:**
    `_escrever_no_heroic` lê, funde e regrava preservando o que é dela; o
    override do Flatpak idem. Rodar a cada transição não acumula nada.

    **NUNCA LEVANTA.** Quem chama é a borda de materialização do daemon, que já
    é best-effort declarada: *"a materialização quebrada não pode derrubar o
    start da emulação"*. Um lançador ilegível ou uma estrada sem ambiente
    devolve nada e segue — e quem quiser a RAZÃO tem o `planejar`, que a diz.

    Devolve as chaves dos cartões em que escreveu, para o journal.

    **A LISTA DE EXCLUSÃO MANDA AQUI TAMBÉM** (01/10/2026): a caixa de um
    emulador excluído não recebe o ambiente, a cópia de um jogo do Heroic
    excluído volta a ficar sem o que é nosso, e (02/10/2026) o `.yml` de um
    jogo excluído do Lutris Flatpak volta a cobrir a caixa — ver
    :class:`NaExclusao`.
    O parâmetro da exclusão existe para a régua; ``None`` lê a lista do dono.

    **UM ESCRITOR POR VEZ (02/10/2026):** a carona inteira roda sob a
    :func:`trava_da_lista` (a lista, o registro das estradas e os arquivos dos
    lançadores), e a lista se lê já com ela na mão. ``espera``: ``None`` é a do
    serviço (:data:`ESPERA_DO_SERVICO_S`); sem a trava no prazo, a carona pula
    esta vez e o diário diz `carona_esperou_a_janela`.
    """
    prazo = ESPERA_DO_SERVICO_S if espera is None else espera
    with trava_da_lista(espera=prazo) as na_mao:
        if not na_mao:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.logging_config import get_logger

                get_logger(__name__).info("carona_esperou_a_janela", espera_s=prazo)
            return ()
        return _curar_na_trava(lar, pasta_do_ambiente, raiz_sistema, exclusao)


def _curar_na_trava(
    lar: Path | None, pasta_do_ambiente: Path | None, raiz_sistema: Path | None,
    exclusao: NaExclusao | None,
) -> tuple[str, ...]:
    """O corpo de :func:`curar_todas_as_estradas`, com a trava na mão."""
    fora = _a_exclusao() if exclusao is None else exclusao
    escritos: list[str] = []
    for chave, atalhos in cartoes_com_estrada():
        try:
            plano = planejar(chave, atalhos, lar, pasta_do_ambiente,
                             raiz_sistema)
            if plano.impedimento or not plano.estradas or not plano.ambiente:
                continue
            estradas = tuple(e for e in plano.estradas
                             if e.app_id.casefold() not in fora.caixas)
            if not estradas:
                continue
            #: O registro de ANTES da escrita vai às cópias: a escrita tira dele
            #: a chave que saiu do ambiente (o `IGNORE` no Modo Nativo), e a
            #: cópia ainda a tem — sem o de antes, ela ficaria lá.
            registro_antes = ler_registro(pasta_do_ambiente)
            escrever_a_estrada(replace(plano, estradas=estradas))
            for estrada in estradas:
                if estrada.tipo == HEROIC_CONFIG:
                    _por_o_nosso_nas_copias(
                        estrada.arquivo.parent, plano.ambiente, pasta_do_ambiente,
                        frozenset(c.arquivo for c in fora.copias),
                        registro_antes.get(str(estrada.arquivo)))
        except Exception:  # pragma: no cover - disco hostil; ver a docstring
            continue
        escritos.append(chave)
    for copia in fora.copias:
        with contextlib.suppress(Exception):
            _sem_o_nosso_no_jogo(Path(copia.arquivo), copia.app, pasta_do_ambiente)
    #: O `.yml` do jogo excluído do Lutris Flatpak cobre a caixa que acabou de
    #: ser escrita (A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01, 02/10/2026).
    _manter_os_ymls(fora.ymls, lar, pasta_do_ambiente)
    return tuple(escritos)


# ── AS CÓPIAS DOS JOGOS DO HEROIC recebem o ambiente de agora ─────────────
#
# AS-SOLUCOES-NOS-LANCADORES-01 (01/10/2026). A escrita acima vai à lista
# GLOBAL do Heroic, e o jogo com cópia própria não a lê mais (o Heroic monta
# `{...globais, ...do jogo}`). Todo jogo INSTALADO tem cópia: o Heroic a grava
# ao instalar, com o `winePrefix`. Medido no disco dela em 01/10, só leitura: a
# global tinha as 8 variáveis da ponte, e a cópia do Guardiões (de 22/09) não
# tinha três: `PROTON_ENABLE_MHWILDS_USB_AUDIO`,
# `PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE` e `SDL_ACCELEROMETER_AS_JOYSTICK`.
# A háptica pelo áudio e o acelerômetro não chegavam ao único jogo instalado
# do Heroic. Era a «dívida aberta» do cabeçalho deste módulo.
#
# A CONTA É A MESMA DA GLOBAL, com o registro da casa: os valores que vão à
# cópia são os mesmos que acabaram de ir à global, então o desfazer do
# uninstall (que lê a cópia pelo registro da casa) os reconhece. As que
# PODEM SER DELA não entram na cópia: numa cópia elas são a escolha dela para
# aquele jogo (:func:`_entrada_da_copia`). O jogo excluído não recebe nada.
def _ambiente_da_copia(ambiente: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in ambiente.items() if k not in PODEM_SER_DELA}


def _unir(*entradas: Entrada | None) -> Entrada:
    """Os valores nossos que QUALQUER uma destas entradas conhece, por chave."""
    fora = Entrada(HEROIC_CONFIG)
    for entrada in entradas:
        for chave, marca in (entrada.chaves.items() if entrada is not None else ()):
            atual = fora.chaves.setdefault(chave, Marca([], marca.antes))
            atual.valores += [v for v in marca.valores if v not in atual.valores]
    return fora


def _por_o_nosso_nas_copias(
    casa: Path, ambiente: dict[str, str], pasta_do_ambiente: Path | None,
    excluidas: frozenset[str], antes: Entrada | None = None,
) -> int:
    """O ambiente de agora em cada cópia com lista própria desta casa.

    ``antes``: o registro da casa de antes da escrita da global, somado ao de
    agora. Devolve quantas cópias mudaram. Cópia ilegível não se reescreve;
    cópia sem lista própria segue a global e fica como está. Nunca levanta.
    """
    entrada = _unir(antes, ler_registro(pasta_do_ambiente).get(str(casa / "config.json")))
    nosso = _ambiente_da_copia(ambiente)
    mudaram = 0
    pasta = casa / _PASTA_DOS_JOGOS_DO_HEROIC
    for arquivo in sorted(pasta.glob("*.json")) if pasta.is_dir() else ():
        if str(arquivo) in excluidas or arquivo.is_symlink() or not arquivo.is_file():
            continue
        try:
            raiz = cast("object", json.loads(arquivo.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
        if not isinstance(raiz, dict):
            continue
        mudou = False
        for jogo in raiz.values():
            lista = jogo.get(CHAVE_DO_HEROIC) if isinstance(jogo, dict) else None
            if not isinstance(jogo, dict) or not isinstance(lista, list):
                continue
            pares = _pares_da_lista(lista)
            novos = _tomar(pares, nosso, _entrada_da_copia(entrada))
            if novos != pares:
                jogo[CHAVE_DO_HEROIC] = [{"key": k, "value": v} for k, v in novos]
                mudou = True
        if mudou:
            try:
                _escrever_atomico(arquivo, json.dumps(raiz, indent=2, ensure_ascii=False))
            except OSError:
                continue
            mudaram += 1
    return mudaram


def frase_das_estradas(escritos: Iterable[str]) -> str:
    """O recibo da carona, para o diário: os lançadores que receberam o ambiente.

    O nome é o do censo (`_ONDE`), e não a chave interna. Vazio = nenhum.
    """
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import _ONDE

    nomes = {k.casefold(): k for k in _ONDE}
    quem = [nomes.get(c, c) for c in escritos]
    if not quem:
        return "Nenhum outro lançador recebeu o ambiente do Hefesto agora."
    return "O ambiente do Hefesto está em: " + ", ".join(quem) + "."


def onde_falta_o_ambiente(
    chave: str, atalhos: tuple[str, ...], *, lar: Path | None = None,
    pasta_do_ambiente: Path | None = None, raiz_sistema: Path | None = None,
    exclusao: NaExclusao | None = None,
) -> tuple[str, ...]:
    """Onde o ambiente de agora NÃO está neste cartão — para a aba Lançadores.

    No Heroic, os nomes dos jogos INSTALADOS cuja lista efetiva (a própria, ou
    a global para quem não tem) não traz o ambiente; nas caixas do Flatpak, os
    `app-id` das caixas sem ele. Vazio quando está tudo no lugar, quando não há
    estrada, ou quando o serviço não publicou o ambiente (não há com o que
    comparar). O excluído não conta: ele está sem o ambiente de propósito.

    SÓ LÊ, e abre disco: quem chama é a vigia da aba, nunca a pintura.
    """
    plano = planejar(chave, atalhos, lar, pasta_do_ambiente, raiz_sistema)
    if plano.impedimento or not plano.estradas or not plano.ambiente:
        return ()
    fora = _a_exclusao() if exclusao is None else exclusao

    def falta_em(pares: Pares, ambiente: dict[str, str]) -> bool:
        #: Uma :data:`DELA_MANDA` presente não falta, com qualquer valor: o
        #: dela manda, e a carona não o trocaria.
        tem = dict(pares)
        return any(tem.get(k) != v and not (k in DELA_MANDA and k in tem)
                   for k, v in ambiente.items())

    #: SÓ O QUE A CARONA ESCREVE: a caixa de um lançador que ela declarou à mão
    #: não está na tabela da carona (:func:`cartoes_com_estrada`), e dizer que
    #: falta ali seria cobrar o que nada põe.
    da_carona = {a.casefold() for _, ats in cartoes_com_estrada() for a in ats}
    faltam: list[str] = []
    for estrada in plano.estradas:
        if estrada.tipo == FLATPAK_OVERRIDE:
            if (estrada.app_id.casefold() in fora.caixas
                    or estrada.app_id.casefold() not in da_carona):
                continue
            cfg = _ler_override(estrada.arquivo)
            pares: Pares = (list(cfg.items("Environment"))
                            if cfg is not None and cfg.has_section("Environment") else [])
            if falta_em(pares, plano.ambiente):
                faltam.append(estrada.app_id)
            continue
        raiz = _ler_heroic(estrada.arquivo)
        global_falta = raiz is None or falta_em(_pares_do_heroic(raiz), plano.ambiente)
        excluidas = {c.arquivo for c in fora.copias}
        from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

        #: OS JOGOS DESTA CASA, e não os do Heroic inteiro: com os dois
        #: instalados, o jogo da outra casa tem a cópia na outra `GamesConfig`.
        biblioteca = censo._heroic(estrada.arquivo.parent)
        pasta = estrada.arquivo.parent / _PASTA_DOS_JOGOS_DO_HEROIC
        for jogo in biblioteca.jogos:
            if not jogo.instalado or "/" in jogo.chave:
                continue
            arquivo = pasta / f"{jogo.chave}.json"
            if str(arquivo) in excluidas:
                continue
            try:
                copia = cast("object", json.loads(arquivo.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                copia = None
            dele = copia.get(jogo.chave) if isinstance(copia, dict) else None
            lista = dele.get(CHAVE_DO_HEROIC) if isinstance(dele, dict) else None
            if isinstance(lista, list):
                if falta_em(_pares_da_lista(lista), _ambiente_da_copia(plano.ambiente)):
                    faltam.append(jogo.nome)
            elif global_falta:
                faltam.append(jogo.nome)
    return tuple(faltam)


# ── O DESFAZER: o uninstall tira exatamente o que é nosso ─────────────────


@dataclass
class Desfeito:
    """O que o desfazer fez num arquivo de lançador."""

    arquivo: Path
    tiradas: list[str] = field(default_factory=list)
    devolvidas: list[str] = field(default_factory=list)
    ficaram: list[str] = field(default_factory=list)
    #: O arquivo nasceu com o Hefesto, e sem o que é nosso ficou vazio: saiu.
    apagado: bool = False
    #: Não abriu, ou não gravou: não se reescreve por cima (ver
    #: :func:`_ler_heroic`), e o registro fica para a próxima vez.
    erro: str = ""
    #: O jogo excluído voltou a ser como era antes da exclusão (02/10/2026).
    voltou: bool = False


def _casas_do_heroic_na_rede(lar: Path) -> list[Path]:
    """Toda casa do Heroic que existe, instalado ou não — a rede do desfazer.

    As do lar e, quando o ambiente desvia o `XDG_CONFIG_HOME`, a nativa de lá:
    a mesma conta das listas de exclusão (:func:`_listas_de_exclusao_padrao`),
    porque o `uninstall.sh` passa o `--lar` e o XDG dela vem do ambiente. A
    regra das casas é do censo (`censo_dos_lancadores.pastas_que_existem`).
    """
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    casas = list(censo.pastas_que_existem("Heroic", lar))
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if os.path.isabs(xdg):
        for casa in censo.pastas_que_existem("Heroic", lar, xdg_config=Path(xdg)):
            if casa not in casas:
                casas.append(casa)
    return casas


def estradas_possiveis(lar: Path) -> list[tuple[Path, str]]:
    """Todo arquivo de lançador em que a cura pode ter escrito, e que existe.

    É a rede de quem escreveu SEM registro: o `config.json` em toda casa do
    Heroic (:func:`_casas_do_heroic_na_rede`), e o override de cada `app-id`
    dos cartões com estrada — instalado ou não, porque desinstalar o lançador
    pelo Flatpak não leva o override.
    """
    achados: list[tuple[Path, str]] = []
    for casa in _casas_do_heroic_na_rede(lar):
        alvo = casa / "config.json"
        if alvo.is_file():
            achados.append((alvo, HEROIC_CONFIG))
    raiz = lar / _PASTA_DOS_OVERRIDES
    for chave, atalhos in cartoes_com_estrada():
        if chave == "heroic":  # a estrada dele é o `config.json` (estradas_do_cartao)
            continue
        for app_id in atalhos:
            alvo = raiz / app_id
            if "." in app_id and alvo.is_file():
                achados.append((alvo, FLATPAK_OVERRIDE))
    return achados


#: A PASTA DAS CÓPIAS POR JOGO do Heroic, dentro da casa dele
#: (`gamesConfigPath` no fonte do Heroic: `<casa>/GamesConfig/<jogo>.json`).
_PASTA_DOS_JOGOS_DO_HEROIC = "GamesConfig"


def copias_por_jogo_do_heroic(lar: Path) -> list[tuple[Path, Path]]:
    """``[(config.json da casa, cópia de um jogo)]`` em toda casa do Heroic.

    **O HEROIC COPIA O AMBIENTE GLOBAL PARA DENTRO DO JOGO — conferência de
    25/09/2026, medido no fonte dele e no disco dela.** O `GameConfigV0` monta
    as opções de um jogo como `{...globais, ...do jogo}`, com
    `enviromentOptions: [...enviromentOptions]` — uma CÓPIA da lista global —,
    e grava tudo em `GamesConfig/<jogo>.json` na primeira vez que ela muda
    qualquer opção daquele jogo (o `setSetting` chama o `flush`). Dali em
    diante a lista do jogo vale SOZINHA: a global não entra mais nele. No disco
    dela, em 25/09, um dos três jogos com configuração própria carregava o
    `SDL_GAMECONTROLLER_IGNORE_DEVICES` e o `PROTON_DISABLE_HIDRAW` copiados em
    22/09 — um uninstall que só limpa a lista global deixa AQUELE jogo sem o
    DualSense físico, que é o defeito que esta sprint existe para fechar.
    """
    achados: list[tuple[Path, Path]] = []
    for casa in _casas_do_heroic_na_rede(lar):
        pasta = casa / _PASTA_DOS_JOGOS_DO_HEROIC
        if not pasta.is_dir():
            continue
        for arq in sorted(pasta.glob("*.json")):
            if arq.is_file() and not arq.is_symlink():
                achados.append((casa / "config.json", arq))
    return achados


def _entrada_da_copia(entrada: Entrada) -> Entrada:
    """O registro do `config.json` da casa, como vale para a cópia de um jogo.

    **SEM AS QUE PODEM SER DELA**, e é o lado reversível: numa cópia por jogo
    um `__GL_SHADER_*` pode ser a escolha dela PARA AQUELE JOGO, e devolver ali
    o «antes» da lista global trocaria o que ela pôs. As do produto saem pelo
    valor nosso, como na lista global.
    """
    #: O «antes» de uma :data:`DELA_MANDA` é o da lista global, e numa cópia o
    #: desfazer o poria num jogo que nunca o teve: na cópia ela vale sem ele.
    #: **E O VALOR DELE, NA CÓPIA, É DELA** (02/10/2026): o Heroic copia a
    #: global para dentro do jogo, e a carona nunca troca a dela. Com o `0` dela
    #: na global antes do Hefesto, o `0` de uma cópia é o dela copiado; lido como
    #: nosso, o uninstall e a exclusão o tiravam, e o jogo voltava ao xalia.
    chaves: dict[str, Marca] = {}
    for k, m in entrada.chaves.items():
        if k in PODEM_SER_DELA:
            continue
        if k not in DELA_MANDA:
            chaves[k] = copy.deepcopy(m)
            continue
        nossos = [v for v in m.valores if v != m.antes]
        if nossos:
            chaves[k] = Marca(nossos, None)
    return Entrada(HEROIC_CONFIG, chaves=chaves)


def _desfazer_na_copia_do_jogo(alvo: Path, entrada: Entrada, feito: Desfeito) -> str | None:
    """A cópia de um jogo sem o que é nosso; ``None`` = igual (ou não é para mexer).

    O Heroic nunca apaga a cópia, e o desfazer também não: só a lista
    `enviromentOptions` de cada jogo muda, e o resto do arquivo passa intacto.
    O texto sai no formato do dono (`JSON.stringify(config, null, 2)`).
    """
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        feito.erro = "não consegui ler — não reescrevo por cima"
        return None
    try:
        raiz = cast("object", json.loads(texto))
    except ValueError:
        raiz = None
    if not isinstance(raiz, dict):
        #: «Não sei» não é zero: um arquivo torto que CITA uma variável nossa
        #: pode estar com ela, e o desfazer diz; um que não cita não é conosco.
        suspeitas = (_DO_PRODUTO_SEM_REGISTRO | set(entrada.chaves)) - PODEM_SER_DELA
        if any(nome in texto for nome in suspeitas):
            feito.erro = "não consegui ler — não reescrevo por cima"
        return None
    mudou = False
    for jogo in raiz.values():
        lista = jogo.get(CHAVE_DO_HEROIC) if isinstance(jogo, dict) else None
        if not isinstance(jogo, dict) or not isinstance(lista, list):
            continue
        pares = _pares_da_lista(lista)
        novos, contas = _desfazer_pares(pares, _entrada_da_copia(entrada))
        feito.tiradas += contas.tiradas
        feito.devolvidas += contas.devolvidas
        feito.ficaram += contas.ficaram
        if novos != pares:
            jogo[CHAVE_DO_HEROIC] = [{"key": k, "value": v} for k, v in novos]
            mudou = True
    return json.dumps(raiz, indent=2, ensure_ascii=False) if mudou else None


def _desfazer_no_heroic(alvo: Path, entrada: Entrada, feito: Desfeito) -> str | None:
    """O texto novo do `config.json` sem o que é nosso; ``""`` = apagar; ``None`` = igual."""
    raiz = _ler_heroic(alvo)
    if raiz is None:
        feito.erro = "não consegui ler — não reescrevo por cima"
        return None
    pares = _pares_do_heroic(raiz)
    novos, contas = _desfazer_pares(pares, copy.deepcopy(entrada))
    feito.tiradas, feito.devolvidas, feito.ficaram = (
        contas.tiradas, contas.devolvidas, contas.ficaram)
    mudou = novos != pares
    padroes = raiz.get("defaultSettings")
    if isinstance(padroes, dict):
        if isinstance(padroes.get(CHAVE_DO_HEROIC), list):
            if mudou:
                padroes[CHAVE_DO_HEROIC] = [{"key": k, "value": v} for k, v in novos]
            if CHAVE_DO_HEROIC in entrada.moldura and not novos:
                del padroes[CHAVE_DO_HEROIC]
                mudou = True
        if "defaultSettings" in entrada.moldura and not padroes:
            del raiz["defaultSettings"]
            mudou = True
    if entrada.nasceu and not raiz:
        return ""
    return json.dumps(raiz, indent=2, ensure_ascii=False) + "\n" if mudou else None


def _desfazer_no_override(alvo: Path, entrada: Entrada, feito: Desfeito) -> str | None:
    """O override sem o que é nosso; ``""`` = apagar; ``None`` = igual."""
    cfg = _ler_override(alvo)
    if cfg is None:
        feito.erro = "não consegui ler — não reescrevo por cima"
        return None
    tem = cfg.has_section("Environment")
    pares: Pares = list(cfg.items("Environment")) if tem else []
    novos, contas = _desfazer_pares(pares, copy.deepcopy(entrada))
    feito.tiradas, feito.devolvidas, feito.ficaram = (
        contas.tiradas, contas.devolvidas, contas.ficaram)
    mudou = novos != pares
    if tem:
        _repor_secao(cfg, "Environment", novos)
        if "Environment" in entrada.moldura and not novos:
            cfg.remove_section("Environment")
            mudou = True
    if entrada.nasceu and not cfg.sections():
        return ""
    return _render_ini(cfg) if mudou else None


def _desfazer_no_arquivo(alvo: Path, entrada: Entrada, *, copia_do_jogo: bool = False,
                         ) -> Desfeito:
    feito = Desfeito(alvo)
    if not alvo.is_file():
        return feito
    if copia_do_jogo:
        desfazer = _desfazer_na_copia_do_jogo
    else:
        desfazer = (_desfazer_no_heroic if entrada.tipo == HEROIC_CONFIG
                    else _desfazer_no_override)
    texto = desfazer(alvo, entrada, feito)
    try:
        if texto == "":
            alvo.unlink()
            feito.apagado = True
        elif texto is not None:
            _escrever_atomico(alvo, texto)
    except OSError as erro:
        feito.erro = f"não consegui gravar ({erro.strerror or erro})"
    return feito


#: O ARQUIVO DA LISTA DE EXCLUSÃO, dentro da configuração — o mesmo
#: `lista_de_exclusao.RELPATH`, repetido aqui porque o desfazer roda com o
#: `python3` do sistema e a lista puxa o pacote. Uma régua segura os dois iguais
#: (`test_o_uninstall_devolve_o_jogo_excluido.py`).
RELPATH_DA_LISTA = "hefesto-dualsense4unix/lista_de_exclusao.json"


def caminho_da_lista(config_home: Path | None = None) -> Path:
    """``$XDG_CONFIG_HOME/hefesto-dualsense4unix/lista_de_exclusao.json``.

    A conta é uma só (`lista_de_exclusao.caminho` pergunta aqui): a trava mora
    ao lado do arquivo, e a janela e o serviço têm de achar a mesma.
    """
    if config_home is None:
        xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
        config_home = Path(xdg) if xdg else Path.home() / ".config"
    return config_home / RELPATH_DA_LISTA


# ── A TRAVA DA LISTA: um escritor por vez ─────────────────────────────────
#
# A-LISTA-DE-EXCLUSAO-TEM-UM-ESCRITOR-POR-VEZ-01 (02/10/2026). A lista de
# exclusão, o registro das estradas e os arquivos dos lançadores têm dois
# processos que leem, juntam e regravam: a janela («Excluir», «Tirar da
# lista», «Aplicar soluções nos lançadores») e o serviço (a carona de cada
# transição). Cada escrita é atômica, e nenhuma é trava: medido num lar de
# mentira com 300 «Excluir» seguidos e a anotação da carona em laço noutro
# processo, 147, 222 e 149 das 300 exclusões sumiram do arquivo. A exclusão que
# some deixa no disco o que ela fez, sem registro para o «Tirar» devolver.
#
# O DONO DA TRAVA É ESTE MÓDULO, e não a lista: o desfazer do uninstall roda
# este arquivo sozinho, com o `python3` do sistema. Só biblioteca padrão.
#
# É REENTRANTE NO MESMO PROCESSO: o «Tirar da lista» de uma caixa chama a
# carona, e a carona chama o `anotar_os_ymls`, com a trava na mão. Um segundo
# `flock` num descritor novo do mesmo arquivo, no mesmo processo, esperaria o
# primeiro. O descritor abre uma vez por processo; o mesmo fio entra de novo
# sem pedir, outro fio do processo espera como outro processo esperaria.

#: O arquivo da trava, ao lado da lista. Nunca sai: apagar um arquivo de
#: `flock` enquanto outro processo o espera daria duas trancas a dois donos.
NOME_DA_TRAVA = ".lista_de_exclusao.trava"

#: Quanto a JANELA espera: o clique dela termina (por delegação, a validar por
#: ela). O desfazer do uninstall espera como ela.
ESPERA_DA_JANELA_S = 5.0

#: Quanto o SERVIÇO espera: a carona é idempotente e a próxima transição a
#: refaz; sem a trava, ela pula a transição e diz `carona_esperou_a_janela`.
ESPERA_DO_SERVICO_S = 1.0

@dataclass
class _Trava:
    """A trava de UM arquivo, neste processo."""

    fio: threading.RLock = field(default_factory=threading.RLock)
    fd: int = -1
    contagem: int = 0


_TRAVAS: dict[str, _Trava] = {}
_TRAVAS_DO_PROCESSO = threading.Lock()


def _esquecer_as_travas_no_filho() -> None:
    """O filho de um `fork` nasce sem trava: o descritor herdado só se fecha.

    Fechar não solta o `flock` do pai (a descrição aberta segue com ele); um
    `LOCK_UN` aqui soltaria.
    """
    global _TRAVAS_DO_PROCESSO
    for trava in _TRAVAS.values():
        if trava.fd >= 0:
            with contextlib.suppress(OSError):
                os.close(trava.fd)
    _TRAVAS.clear()
    _TRAVAS_DO_PROCESSO = threading.Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_esquecer_as_travas_no_filho)


def _travar_o_arquivo(alvo: Path, prazo: float, criar: bool) -> int | None:
    """O descritor com o `flock` exclusivo; ``-1`` = segue sem; ``None`` = o prazo passou.

    Segue sem trava (``-1``) onde não há `fcntl`, onde a pasta não existe e
    ``criar`` é falso (o desfazer do uninstall não cria a configuração dela),
    e onde o arquivo não abre: é o comportamento de antes, e recusar ali
    deixaria a janela sem «Excluir» por uma permissão.
    """
    try:
        import fcntl
    except ImportError:  # pragma: no cover - só Linux roda isto
        return -1
    if not criar and not alvo.parent.is_dir():
        return -1
    try:
        if criar:
            alvo.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(alvo, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return -1
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        pass
    except OSError:
        os.close(fd)
        return -1
    if time.monotonic() >= prazo:
        os.close(fd)
        return None
    return _esperar_na_fila(fcntl, fd, prazo)


def _esperar_na_fila(fcntl: ModuleType, fd: int, prazo: float) -> int | None:
    """Espera o `flock` na fila do núcleo, com prazo; ``fd`` / ``-1`` / ``None``.

    QUEM ESPERA ESTÁ NA FILA, e não perguntando de tempos em tempos: medido
    em 02/10/2026, quem perguntava a cada 20 ms perdia para um escritor que
    retoma a trava logo depois de soltá-la (9 de 10 esperas passaram de 2 s;
    a régua da corrida reprovou 2 de 12 vezes com o «Excluir» voltando
    «erro»). Na fila, o `LOCK_UN` do outro acorda quem espera, e a espera
    foi de no máximo 4 ms. O `flock` bloqueante não tem prazo: ele corre num
    fio próprio, e quem chama espera o fio até o prazo. Se o prazo passa, o
    descritor fica com o fio, que solta e fecha assim que pegar a trava;
    ninguém mais o fecha (um descritor fechado por baixo de um `flock` em
    curso pode ter o número reusado e travar outro arquivo).
    """
    pegou = threading.Event()
    guarda = threading.Lock()
    desistiu = [False]
    falhou = [False]

    def esperar() -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError:
            falhou[0] = True
        with guarda:
            if desistiu[0]:
                _soltar(fd)
                return
            pegou.set()

    threading.Thread(target=esperar, name="trava-da-lista", daemon=True).start()
    pegou.wait(max(0.0, prazo - time.monotonic()))
    with guarda:
        if not pegou.is_set():
            desistiu[0] = True
            return None
    if falhou[0]:
        with contextlib.suppress(OSError):
            os.close(fd)
        return -1
    return fd


def _soltar(fd: int) -> None:
    """Solta o `flock` e fecha. O `LOCK_UN` vem antes: um filho de `fork` que
    ainda tenha a cópia do descritor não segura a trava depois do dono."""
    with contextlib.suppress(OSError, ImportError):
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)
    with contextlib.suppress(OSError):
        os.close(fd)


@contextlib.contextmanager
def trava_da_lista(lista: Path | None = None, *, espera: float | None = None,
                   criar: bool = True) -> Iterator[bool]:
    """Um escritor por vez na lista de exclusão e no que ela anota.

    Rende ``True`` com a trava na mão (ou sem trava possível, ver
    :func:`_travar_o_arquivo`), e ``False`` quando o prazo passou: quem chama
    não escreve nada. Quem já a segura neste fio entra sem esperar.
    ``espera``: ``None`` é a da janela (:data:`ESPERA_DA_JANELA_S`).
    """
    alvo = (caminho_da_lista() if lista is None else lista).parent / NOME_DA_TRAVA
    chave = os.path.realpath(alvo)
    with _TRAVAS_DO_PROCESSO:
        trava = _TRAVAS.setdefault(chave, _Trava())
    teto = max(0.0, ESPERA_DA_JANELA_S if espera is None else espera)
    prazo = time.monotonic() + teto
    if not trava.fio.acquire(timeout=teto):
        yield False
        return
    try:
        if trava.contagem == 0:
            fd = _travar_o_arquivo(alvo, prazo, criar)
            if fd is None:
                yield False
                return
            trava.fd = fd
        trava.contagem += 1
        try:
            yield True
        finally:
            trava.contagem -= 1
            if trava.contagem == 0:
                fd, trava.fd = trava.fd, -1
                if fd >= 0:
                    _soltar(fd)
    finally:
        trava.fio.release()


def _ler_a_lista_crua(arquivo: Path) -> tuple[list[CopiaDoJogo], list[YmlDoJogo]] | None:
    """As cópias do Heroic e os `.yml` do Lutris que a lista anotou, lida como JSON cru.

    Ausente = ``([], [])``; existe e não se lê = ``None``. Só biblioteca padrão:
    quem a lê aqui é o desfazer do uninstall.
    """
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [], []
    except OSError:
        return None
    try:
        dado = cast("object", json.loads(texto))
    except ValueError:
        return None
    jogos = dado.get("jogos") if isinstance(dado, dict) else None
    if not isinstance(jogos, list):
        return None
    copias: list[CopiaDoJogo] = []
    ymls: list[YmlDoJogo] = []
    for jogo in jogos:
        if not isinstance(jogo, dict):
            continue
        heroic, lutris = jogo.get("heroic"), jogo.get("lutris")
        copias += [c for c in (CopiaDoJogo.de_dado(x)
                               for x in (heroic if isinstance(heroic, list) else ())) if c]
        ymls += [y for y in (YmlDoJogo.de_dado(x)
                             for x in (lutris if isinstance(lutris, list) else ())) if y]
    return copias, ymls


def _sem_o_cache_que_a_exclusao_copiou(copia: CopiaDoJogo, entrada: Entrada) -> list[str]:
    """A cópia que a exclusão CRIOU da lista global perde o cache de shader nosso.

    Numa cópia por jogo o `__GL_SHADER_*` é lido como «pode ser dela»
    (:func:`_entrada_da_copia`), mas numa cópia que a exclusão criou da global
    (`sem_lista`) ele veio da global, com o valor que a carona pôs lá. Medido
    na O-UNINSTALL-DEVOLVE-O-JOGO-EXCLUIDO-01: os dois ficavam no jogo depois do
    uninstall. Só sai o par que ainda tem o valor que a exclusão copiou e que o
    registro da casa diz que é nosso; o «antes» dela volta no lugar. Devolve as
    chaves tiradas. Nunca levanta.
    """
    alvo = Path(copia.arquivo)
    try:
        raiz = cast("object", json.loads(alvo.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []
    jogo = raiz.get(copia.app) if isinstance(raiz, dict) else None
    lista = jogo.get(CHAVE_DO_HEROIC) if isinstance(jogo, dict) else None
    if not isinstance(raiz, dict) or not isinstance(jogo, dict) or not isinstance(lista, list):
        return []
    pares = _pares_da_lista(lista)
    copiados = set(copia.depois)
    chaves = [k for k, m in entrada.chaves.items() if k in PODEM_SER_DELA and any(
        a == k and (a, b) in copiados and b in m.valores for a, b in pares)]
    if not chaves:
        return []
    contas = _Contas()
    novos = _devolver_chaves(pares, chaves, copy.deepcopy(entrada), contas)
    jogo[CHAVE_DO_HEROIC] = [{"key": k, "value": v} for k, v in novos]
    try:
        _escrever_atomico(alvo, json.dumps(raiz, indent=2, ensure_ascii=False))
    except OSError:
        return []
    return contas.tiradas


def _devolver_os_excluidos(listas: Iterable[Path],
                           registro: dict[str, Entrada]) -> list[Desfeito]:
    """A volta de cada jogo excluído fora da Steam, antes de tirar o nosso.

    A mesma volta do «Tirar da lista» (:func:`devolver_ao_jogo_do_heroic` e
    :func:`devolver_ao_jogo_do_lutris`): exata se ninguém mexeu, ou só os
    pares da exclusão. O `.yml` mexido sem o PyYAML fica, e é sobra.
    """
    feitos: list[Desfeito] = []
    for arquivo in dict.fromkeys(listas):
        lido = _ler_a_lista_crua(arquivo)
        if lido is None:
            feitos.append(Desfeito(arquivo, erro="não consegui ler a lista de exclusão — "
                                   "os jogos excluídos ficam para o desfazer de depois"))
            continue
        copias, ymls = lido
        for copia in copias:
            feito = Desfeito(Path(copia.arquivo))
            status = devolver_ao_jogo_do_heroic([copia])
            if status == "erro":
                feito.erro = ("não consegui devolver o jogo excluído — fica para o "
                              "desfazer de depois")
            feito.voltou = status == "feito"
            if copia.sem_lista:
                casa = str(Path(copia.arquivo).parent.parent / "config.json")
                feito.tiradas = _sem_o_cache_que_a_exclusao_copiou(
                    copia, registro.get(casa, Entrada(HEROIC_CONFIG)))
            feitos.append(feito)
        for yml in ymls:
            feito = Desfeito(Path(yml.arquivo))
            status = devolver_ao_jogo_do_lutris([yml])
            if status == "ficou":
                feito.erro = ("ela mexeu nele depois da exclusão, e sem o PyYAML eu não "
                              "escrevo YAML à mão — fica para o desfazer de depois")
            elif status == "erro":
                feito.erro = ("não consegui devolver o jogo excluído — fica para o "
                              "desfazer de depois")
            feito.voltou = status == "feito"
            feitos.append(feito)
    return feitos


def desfazer_as_estradas(pastas_do_ambiente: Iterable[Path],
                         lar: Path | None = None,
                         listas_de_exclusao: Iterable[Path] = (),
                         ) -> tuple[list[Desfeito], bool]:
    """Tira de todo lançador o que o Hefesto escreveu. ``(o que fez, completo)``.

    Os arquivos vêm do registro de cada pasta (a do ``XDG_STATE_HOME`` e a do
    lar, quando são duas) e da rede de :func:`estradas_possiveis` — e, depois
    deles, as cópias por jogo que o Heroic tirou da lista global
    (:func:`copias_por_jogo_do_heroic`), lidas com o registro do `config.json`
    da mesma casa. Completo, o registro sai; com um arquivo que não abriu, o
    que é dele fica anotado na primeira pasta, para o desfazer de novo — e a
    resposta é ``False``.

    **O JOGO EXCLUÍDO VOLTA PRIMEIRO — 02/10/2026,
    O-UNINSTALL-DEVOLVE-O-JOGO-EXCLUIDO-01.** A exclusão também escreve nos
    arquivos dos lançadores (a lista própria do jogo do Heroic, o `.yml` do
    jogo do Lutris Flatpak), e a anotação da volta mora na lista de exclusão.
    Medido num lar de mentira: sem ela, o jogo do Heroic que seguia a global
    saía do uninstall com uma lista própria (e o cache de shader nosso
    dentro), e não seguia mais a global dela. Cada `listas_de_exclusao` é lida
    como JSON cru, e a volta de cada jogo vem antes de tirar o nosso.

    **ESPERA COMO A JANELA (02/10/2026):** a trava da lista
    (:func:`trava_da_lista`) é a mesma da janela e do serviço, e sem ela no
    prazo nada se escreve: o desfazer fica para depois, com o registro
    intacto. A pasta da configuração dela não nasce daqui.
    """
    with trava_da_lista(criar=False) as na_mao:
        if not na_mao:
            return [Desfeito(caminho_da_lista(), erro=(
                "a lista de exclusão está sendo escrita agora — o desfazer fica para "
                "depois"))], False
        return _desfazer_na_trava(pastas_do_ambiente, lar, listas_de_exclusao)


def _desfazer_na_trava(pastas_do_ambiente: Iterable[Path], lar: Path | None,
                       listas_de_exclusao: Iterable[Path]) -> tuple[list[Desfeito], bool]:
    """O corpo de :func:`desfazer_as_estradas`, com a trava na mão."""
    lar = Path.home() if lar is None else lar
    pastas = list(pastas_do_ambiente)
    registro: dict[str, Entrada] = {}
    for pasta in pastas:
        for caminho, entrada in ler_registro(pasta).items():
            registro.setdefault(caminho, entrada)
    alvos = dict(registro)
    for arquivo, tipo in estradas_possiveis(lar):
        alvos.setdefault(str(arquivo), Entrada(tipo))
    feitos: list[Desfeito] = _devolver_os_excluidos(listas_de_exclusao, registro)
    sobrou: dict[str, Entrada] = {}
    for caminho, entrada in alvos.items():
        feito = _desfazer_no_arquivo(Path(caminho), entrada)
        feitos.append(feito)
        if feito.erro and caminho in registro:
            sobrou[caminho] = entrada
    for casa, copia in copias_por_jogo_do_heroic(lar):
        entrada = registro.get(str(casa), Entrada(HEROIC_CONFIG))
        feito = _desfazer_no_arquivo(copia, entrada, copia_do_jogo=True)
        feitos.append(feito)
        #: A cópia que não abriu segura o registro da CASA: é ele que diz, no
        #: desfazer de depois, quais valores são nossos.
        if feito.erro and str(casa) in registro:
            sobrou[str(casa)] = registro[str(casa)]
    for i, pasta in enumerate(pastas):
        with contextlib.suppress(OSError):
            gravar_registro(sobrou if i == 0 else {}, pasta)
    return feitos, not any(f.erro for f in feitos)


def frase_do_desfeito(feito: Desfeito) -> str:
    """A linha que o uninstall diz sobre um arquivo — ``""`` quando não houve nada."""
    partes: list[str] = []
    if feito.erro:
        partes.append(feito.erro)
    if feito.tiradas:
        partes.append("tirei " + ", ".join(feito.tiradas))
    if feito.devolvidas:
        partes.append("devolvi o seu valor de antes em " + ", ".join(feito.devolvidas))
    if feito.ficaram:
        partes.append("ficaram as que você mudou depois do Hefesto: "
                      + ", ".join(feito.ficaram))
    if feito.apagado:
        partes.append("o arquivo nasceu com o Hefesto e saiu junto")
    if feito.voltou:
        partes.insert(0, "o jogo excluído voltou a ser como era antes da exclusão")
    return f"{feito.arquivo}: " + "; ".join(partes) if partes else ""


# ── A EXCLUSÃO: o jogo e a caixa que ela tirou do Hefesto ──────────────────
#
# OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01, a metade dos outros
# lançadores (01/10/2026). O jogo excluído vê o controle como se o Hefesto não
# estivesse instalado; fora da Steam, o que o Hefesto põe nele é ESTE ambiente.
#
# MEDIDO ANTES DA CURA, num lar de mentira: excluir o jogo do Heroic deixava o
# `SDL_GAMECONTROLLER_IGNORE_DEVICES` e o `PROTON_DISABLE_HIDRAW` na cópia
# dele, e excluir o RetroArch deixava os dois na caixa — que a carona da
# transição seguinte reescrevia. Com a janela do excluído em foco o daemon
# liga o Modo Nativo (sem controle virtual), e o jogo ficava sem controle
# NENHUM: o físico escondido pelo ambiente, e o virtual desligado.
#
# A UNIDADE É A DA ESTRADA. O Heroic monta as opções de um jogo como
# `{...globais, ...do jogo}` (`GameConfigV0.getSettings`, lido no fonte dele em
# 01/10): a lista própria do jogo SUBSTITUI a global, e é por ela que um jogo
# sai sozinho. A caixa do Flatpak é uma só para todos os jogos do emulador — e
# o emulador já entra na lista inteiro, «todos os jogos».
@dataclass(frozen=True)
class CopiaDoJogo:
    """O que a exclusão fez na cópia de UM jogo do Heroic — e como voltar."""

    #: `<casa do Heroic>/GamesConfig/<app>.json`.
    arquivo: str
    #: O `app_name` do jogo, que é a chave dentro do arquivo.
    app: str
    #: O arquivo não existia: a volta o apaga, se ninguém mexeu nele.
    nasceu: bool = False
    #: O arquivo existia sem a chave do jogo.
    sem_jogo: bool = False
    #: O jogo seguia a lista GLOBAL: a volta tira a lista própria, e ele volta
    #: a segui-la (com a carona que a mantém).
    sem_lista: bool = False
    #: A lista que valia para o jogo antes da exclusão, e a que ficou.
    antes: tuple[tuple[str, str], ...] = ()
    depois: tuple[tuple[str, str], ...] = ()
    #: O prefixo PRÓPRIO do jogo (`winePrefix` da cópia), quando há: o device
    #: KS e as camadas Vulkan moram lá.
    prefixo: str = ""

    def como_dado(self) -> dict[str, object]:
        """O dicionário que vai ao JSON da lista de exclusão."""
        return {"arquivo": self.arquivo, "app": self.app, "nasceu": self.nasceu,
                "sem_jogo": self.sem_jogo, "sem_lista": self.sem_lista,
                "antes": [list(p) for p in self.antes],
                "depois": [list(p) for p in self.depois], "prefixo": self.prefixo}

    @classmethod
    def de_dado(cls, dado: object) -> CopiaDoJogo | None:
        """A cópia lida do JSON; torta = ``None``."""
        if not isinstance(dado, dict):
            return None
        arquivo, app = dado.get("arquivo"), dado.get("app")
        if not isinstance(arquivo, str) or not isinstance(app, str) or not app:
            return None

        def pares(cru: object) -> tuple[tuple[str, str], ...]:
            return tuple((str(p[0]), str(p[1])) for p in (cru if isinstance(cru, list) else ())
                         if isinstance(p, list | tuple) and len(p) == 2)

        prefixo = dado.get("prefixo")
        return cls(arquivo, app, bool(dado.get("nasceu")), bool(dado.get("sem_jogo")),
                   bool(dado.get("sem_lista")), pares(dado.get("antes")),
                   pares(dado.get("depois")), prefixo if isinstance(prefixo, str) else "")


@dataclass(frozen=True)
class YmlDoJogo:
    """O que a exclusão fez no `.yml` de UM jogo do Lutris Flatpak — e como voltar.

    A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01 (02/10/2026): a camada que só este jogo
    lê é o `system.env` do `games/<configpath>.yml` dele, e o Lutris a põe por
    cima do ambiente da caixa (`monitored_command.get_child_environment` e
    `runners/runner.py:292-293`, lidos no 0.5.22 instalado nela).
    """

    #: `<configuração do Lutris>/games/<configpath>.yml`.
    arquivo: str
    #: O texto inteiro de antes da exclusão, para a volta byte a byte. ``None``
    #: quando ela mexeu no arquivo e a carona escreveu de novo por cima: aí a
    #: volta é só pelos pares.
    antes: str | None
    #: O `sha256` do texto que a exclusão (ou a carona dela) gravou por último.
    depois: str
    #: Os pares que a exclusão pôs em `system.env`, e só os que não estavam lá.
    pares: tuple[tuple[str, str], ...] = ()
    #: As peças que o arquivo não tinha e a exclusão criou (`system`, `env`).
    moldura: tuple[str, ...] = ()

    def como_dado(self) -> dict[str, object]:
        """O dicionário que vai ao JSON da lista de exclusão."""
        return {"arquivo": self.arquivo, "antes": self.antes, "depois": self.depois,
                "pares": [list(p) for p in self.pares], "moldura": list(self.moldura)}

    @classmethod
    def de_dado(cls, dado: object) -> YmlDoJogo | None:
        """O registro lido do JSON; torto = ``None``."""
        if not isinstance(dado, dict):
            return None
        arquivo, depois, antes = dado.get("arquivo"), dado.get("depois"), dado.get("antes")
        if not isinstance(arquivo, str) or not arquivo or not isinstance(depois, str):
            return None
        cru = dado.get("pares")
        pares = tuple((str(p[0]), str(p[1])) for p in (cru if isinstance(cru, list) else ())
                      if isinstance(p, list | tuple) and len(p) == 2)
        moldura = dado.get("moldura")
        return cls(arquivo, antes if isinstance(antes, str) else None, depois, pares,
                   tuple(str(x) for x in moldura) if isinstance(moldura, list) else ())


@dataclass(frozen=True)
class NaExclusao:
    """O que a carona pula: as caixas excluídas e as cópias a manter limpas."""

    #: Os `app-id` das caixas excluídas, em `casefold`.
    caixas: frozenset[str] = frozenset()
    copias: tuple[CopiaDoJogo, ...] = ()
    #: Os `.yml` dos jogos excluídos do Lutris Flatpak, que a carona mantém
    #: cobrindo a caixa (02/10/2026).
    ymls: tuple[YmlDoJogo, ...] = ()


def _a_exclusao() -> NaExclusao:
    """A lista do dono (`lista_de_exclusao`), lida tarde. Nunca levanta.

    O import é tardio pelo mesmo motivo do cabeçalho: o desfazer do uninstall
    roda este arquivo com o `python3` do sistema, e a lista puxa o pacote.
    """
    try:
        from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx

        return lx.o_que_a_carona_pula()
    except Exception:
        return NaExclusao()


def _sem_o_nosso_no_jogo(
    alvo: Path, app: str, pasta_do_ambiente: Path | None = None,
) -> tuple[str, CopiaDoJogo | None]:
    """A cópia do jogo `app` com a lista própria, sem nada do que é nosso.

    O que é nosso é o que o desfazer do uninstall tiraria da mesma cópia
    (:func:`_desfazer_pares`, com o registro da casa sem as que podem ser
    dela): é a lista do jogo «como se o Hefesto não estivesse instalado».
    Status: ``"feito"`` | ``"nada"`` | ``"erro"``. Nunca levanta.
    """
    casa = alvo.parent.parent
    nasceu = not alvo.exists()
    try:
        raiz = {} if nasceu else cast("object", json.loads(alvo.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return "erro", None
    if not isinstance(raiz, dict):
        return "erro", None
    jogo = raiz.get(app)
    sem_jogo = not isinstance(jogo, dict)
    if not isinstance(jogo, dict):
        jogo = {}
    propria = jogo.get(CHAVE_DO_HEROIC)
    sem_lista = not isinstance(propria, list)
    if isinstance(propria, list):
        pares = _pares_da_lista(propria)
    else:
        global_ = _ler_heroic(casa / "config.json")
        if global_ is None:
            return "erro", None
        pares = _pares_do_heroic(global_)
    entrada = ler_registro(pasta_do_ambiente).get(
        str(casa / "config.json"), Entrada(HEROIC_CONFIG))
    novos, _ = _desfazer_pares(pares, _entrada_da_copia(entrada))
    prefixo = jogo.get("winePrefix")
    copia = CopiaDoJogo(
        str(alvo), app, nasceu, sem_jogo, sem_lista, tuple(pares), tuple(novos),
        prefixo if isinstance(prefixo, str) else "")
    if not sem_lista and novos == pares:
        return "nada", copia
    jogo[CHAVE_DO_HEROIC] = [{"key": k, "value": v} for k, v in novos]
    raiz[app] = jogo
    if nasceu:
        #: A forma que o próprio Heroic grava (`flush` do `GameConfigV0`).
        raiz.setdefault("version", "v0")
        raiz.setdefault("explicit", True)
    try:
        _escrever_atomico(alvo, json.dumps(raiz, indent=2, ensure_ascii=False))
    except OSError:
        return "erro", None
    return "feito", copia


def jogos_do_heroic_pela_janela(classe: str, lar: Path | None = None) -> list[Path]:
    """As cópias (`GamesConfig/<app>.json`) dos jogos do Heroic com esta janela.

    Quem diz qual jogo anuncia qual janela é o censo
    (`JogoDoLancador.classe_de_janela`); a casa é a que ele leu, e com os dois
    Heroic instalados cada jogo fica na dele. O arquivo pode ainda não
    existir: é onde a cópia nasce.
    """
    alvo = classe.strip()
    if not alvo:
        return []
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    vistos: list[Path] = []
    for biblioteca in censo.bibliotecas_por_casa("Heroic", lar):
        if biblioteca.onde is None:
            continue
        pasta = biblioteca.onde / _PASTA_DOS_JOGOS_DO_HEROIC
        for jogo in biblioteca.jogos:
            if jogo.classe_de_janela == alvo and "/" not in jogo.chave:
                arquivo = pasta / f"{jogo.chave}.json"
                if arquivo not in vistos:
                    vistos.append(arquivo)
    return vistos


def tirar_o_nosso_do_jogo_do_heroic(
    classe: str, *, lar: Path | None = None, pasta_do_ambiente: Path | None = None,
) -> tuple[tuple[CopiaDoJogo, ...], str]:
    """O jogo do Heroic com esta janela passa a ter a lista própria sem o nosso.

    Devolve ``(o que fez, status)``: ``"feito"`` | ``"nada"`` | ``"erro"``.
    Com erro numa cópia, as que já foram feitas voltam — tudo ou nada.
    """
    feitas: list[CopiaDoJogo] = []
    status = "nada"
    for alvo in jogos_do_heroic_pela_janela(classe, lar):
        st, copia = _sem_o_nosso_no_jogo(alvo, alvo.stem, pasta_do_ambiente)
        if st == "erro" or copia is None:
            devolver_ao_jogo_do_heroic(feitas)
            return (), "erro"
        feitas.append(copia)
        if st == "feito":
            status = "feito"
    return tuple(feitas), status


def devolver_ao_jogo_do_heroic(copias: Iterable[CopiaDoJogo]) -> str:
    """A volta: a cópia de cada jogo como estava antes da exclusão.

    Se ninguém mexeu na cópia desde a exclusão, ela volta EXATA (a lista de
    antes, ou nenhuma lista própria, ou nenhum arquivo). Se o Heroic ou ela
    mexeu, o que mudou fica e só os pares que a exclusão tirou voltam, sem
    passar por cima de uma chave que esteja lá. Status: ``"feito"`` |
    ``"nada"`` | ``"erro"``. Nunca levanta.
    """
    status = "nada"
    for copia in copias:
        alvo = Path(copia.arquivo)
        try:
            raiz = cast("object", json.loads(alvo.read_text(encoding="utf-8")))
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            status = "erro"
            continue
        jogo = raiz.get(copia.app) if isinstance(raiz, dict) else None
        if not isinstance(raiz, dict) or not isinstance(jogo, dict):
            continue
        atual = _pares_da_lista(jogo.get(CHAVE_DO_HEROIC))
        tem_lista = isinstance(jogo.get(CHAVE_DO_HEROIC), list)
        #: JÁ VOLTOU (02/10/2026, O-UNINSTALL-DEVOLVE-O-JOGO-EXCLUIDO-01): o
        #: desfazer adiado do uninstall roda de novo sobre a mesma lista, e a
        #: volta parcial reporia na cópia os pares que a exclusão tirou.
        if (copia.sem_lista and not tem_lista) or (
                not copia.sem_lista and tem_lista and tuple(atual) == copia.antes):
            continue
        intacta = tem_lista and tuple(atual) == copia.depois
        if intacta and copia.sem_lista:
            del jogo[CHAVE_DO_HEROIC]
        elif intacta:
            jogo[CHAVE_DO_HEROIC] = [{"key": k, "value": v} for k, v in copia.antes]
        else:
            tem = {k for k, _ in atual}
            voltam = [(k, v) for k, v in copia.antes
                      if (k, v) not in copia.depois and k not in tem]
            if not voltam:
                continue
            jogo[CHAVE_DO_HEROIC] = [{"key": k, "value": v} for k, v in atual + voltam]
        try:
            if intacta and copia.sem_jogo and not jogo:
                del raiz[copia.app]
                if copia.nasceu and set(raiz) <= {"version", "explicit"}:
                    alvo.unlink()
                    status = "feito"
                    continue
            _escrever_atomico(alvo, json.dumps(raiz, indent=2, ensure_ascii=False))
        except OSError:
            status = "erro"
            continue
        if status != "erro":
            status = "feito"
    return status


def _override_da_caixa(app_id: str, lar: Path) -> Path:
    return lar / _PASTA_DOS_OVERRIDES / app_id


def tirar_o_nosso_da_caixa(
    app_ids: Iterable[str], *, lar: Path | None = None,
    pasta_do_ambiente: Path | None = None,
) -> str:
    """A caixa do Flatpak destes `app-id` sem o ambiente que é nosso.

    É o desfazer do uninstall, recortado para estas caixas: o valor dela de
    antes volta, o que ela mudou fica, o arquivo que nasceu com o Hefesto
    sai. A entrada da caixa sai do registro: a carona não escreve numa caixa
    excluída, e a volta («Tirar da lista») é a carona escrevendo de novo.
    Status: ``"feito"`` | ``"nada"`` | ``"erro"``. Nunca levanta.
    """
    lar = Path.home() if lar is None else lar
    try:
        registro = ler_registro(pasta_do_ambiente)
    except Exception:  # pragma: no cover - ler_registro já não levanta
        return "erro"
    mexeu_no_registro = False
    status = "nada"
    for app_id in dict.fromkeys(a for a in app_ids if "." in a):
        alvo = _override_da_caixa(app_id, lar)
        if not alvo.is_file():
            continue
        entrada = registro.get(str(alvo), Entrada(FLATPAK_OVERRIDE))
        feito = _desfazer_no_arquivo(alvo, entrada)
        if feito.erro:
            return "erro"
        if str(alvo) in registro:
            del registro[str(alvo)]
            mexeu_no_registro = True
        if feito.tiradas or feito.devolvidas or feito.apagado:
            status = "feito"
    if mexeu_no_registro:
        try:
            gravar_registro(registro, pasta_do_ambiente)
        except OSError:
            return "erro"
    return status


# ── A CAMADA DO JOGO DO LUTRIS: o `system.env` do `.yml` do excluído ───────
#
# A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01 (02/10/2026). A caixa do Lutris Flatpak
# é uma só para todos os jogos dele, e a exclusão é de UM jogo: tirar o
# ambiente da caixa tiraria o Hefesto de todos, e deixá-lo mantinha o jogo
# excluído com o físico escondido e o Modo Nativo ligado em foco — zero
# controles. Medido num lar de mentira na integração: a caixa seguia com as 9.
#
# O LUTRIS PÕE O AMBIENTE DO JOGO POR CIMA DO DA CAIXA (0.5.22, lido no fonte
# instalado nela): `get_child_environment` faz `system.get_environment()` e
# depois `env.update(self.env)` (`monitored_command.py:150-154`), e o `self.env`
# traz o `system.env` do `.yml` do jogo por último (`runners/runner.py:292-293`).
# Uma chave com valor `''` passa e cobre a da caixa; uma chave NULA é pulada
# (`monitored_command.py:141-142`), e aí vale a da caixa.
#
# O LUTRIS NATIVO NÃO GANHA CAMADA: o ambiente do Hefesto só chega ao jogo dele
# pela caixa do Flatpak (a carona não tem estrada para o nativo), e um `.yml`
# com valores nossos ali mudaria o jogo em vez de devolvê-lo.
#
# O ARQUIVO SE LÊ E SE ESCREVE COM O PyYAML, o mesmo leitor do Lutris
# (`util/yaml.py`: `safe_load` e `safe_dump(..., default_flow_style=False)`). O
# import é tardio: o desfazer do uninstall roda este arquivo com o `python3` do
# sistema, e sem o PyYAML a volta é só a exata (:func:`devolver_ao_jogo_do_lutris`).

#: A caixa do Lutris Flatpak.
_LUTRIS_APP_ID = "net.lutris.Lutris"

#: O «NÃO VEIO» DE CADA LEITOR: o valor que o leitor de uma família de variáveis
#: lê como se ela não tivesse vindo. Nunca nulo (o Lutris pula a chave nula).
#:
#: * ``SDL_`` → ``""``. MEDIDO em 02/10/2026 no SDL2 2.32.10 do runtime da Steam
#:   (`SDL_GetHintBoolean` por `ctypes`, sem iniciar subsistema nenhum): com o
#:   valor vazio, as três dicas booleanas devolvem o padrão, como ausentes. A
#:   lista do `SDL_GAMECONTROLLER_IGNORE_DEVICES` vazia não ignora aparelho
#:   nenhum (lido, não medido: a função que a lê é interna). O SDL do runtime do
#:   Proton é da mesma série, e fica a confirmar nele;
#: * ``PROTON_`` → ``""``. O script do Proton (GE-Proton10-34) lê as opções dele
#:   por `nonzero` (`len(s) > 0 and s != "0"`, `proton:167-168`, pela
#:   `check_environment`, `:1733-1740`): `''` desliga como a ausência, mas a
#:   presença cala os padrões que o próprio script poria. As três `PROTON_*` de
#:   hoje não passam pelo `check_environment`: quem as lê é o Wine, depois do
#:   script, e o efeito do `''` no jogo não foi medido além disso;
#: * o par ``__GL_SHADER_*`` FICA FORA: o leitor é o driver fechado da NVIDIA, e
#:   o efeito do `''` não está medido (ele pode desligar o cache). Por
#:   delegação, a validar por ela: sem a medida, o jogo excluído do Lutris herda
#:   da caixa o cache de shader, que não toca o controle. Com um «antes» dela no
#:   registro da caixa, o `.yml` leva o dela;
#: * o ``PROTON_USE_XALIA`` não tem UM valor de «não veio»: ele depende do jogo
#:   (:data:`_NAO_VEIO_POR_JOGO`).
_NAO_VEIO: tuple[tuple[str, str], ...] = (("SDL_", ""), ("PROTON_", ""))

#: O «NÃO VEIO» QUE DEPENDE DO JOGO — 02/10/2026,
#: O-JOGO-EXCLUIDO-DO-LUTRIS-VOLTA-AO-XALIA-DO-PROTON-01. Lido no GE-Proton 11-7
#: (`proton:2527-2533`) e no 10-34 (`:2093-2099`) instalados nela, só leitura: se
#: `PROTON_USE_XALIA` não veio, o script põe `0` quando o appid está em
#: `noxalia` e, senão, põe `1` E `XALIA_SUPPORTED_ONLY=1` (a menos que a
#: configuração de compatibilidade traga `xalia`). Quem lê o
#: `XALIA_SUPPORTED_ONLY` é o próprio xalia (`share/xalia/main.gudl:1477-1479`).
#: Logo o par é o padrão do jogo que abre pelo script do Proton; com o driver
#: Wayland, o script põe `0` por cima de qualquer valor (11-7 `:2621-2623`), como
#: no padrão. O Wine sem o script do Proton não põe a variável, e o
#: `explorer.exe` sem ela não sobe o xalia: ali o `0` da caixa É o padrão, e a
#: camada não cobre nada. Quem diz por qual dos dois o jogo abre é o censo
#: (`JogoDoLancador.pelo_proton`). Por delegação, a validar por ela; o preço: um
#: jogo cujo appid o script põe em `noxalia` (cinco da Steam no 11-7,
#: `:1752-1761`) recebe o xalia, porque com a variável presente o script não
#: decide. O diário diz `camada_do_lutris_xalia par=1` com o jogo.
_NAO_VEIO_POR_JOGO: dict[str, tuple[tuple[str, str], ...]] = {
    "PROTON_USE_XALIA": (("PROTON_USE_XALIA", "1"), ("XALIA_SUPPORTED_ONLY", "1")),
}

#: As chaves sem UM valor de «não veio» (:func:`nao_veio` devolve ``None``).
_SEM_NAO_VEIO: frozenset[str] = frozenset(_NAO_VEIO_POR_JOGO)

#: O par do xalia, que entra e sai junto: as chaves que a camada põe por ele.
_PAR_DO_XALIA: frozenset[str] = frozenset(
    k for pares in _NAO_VEIO_POR_JOGO.values() for k, _ in pares)


def nao_veio(chave: str) -> str | None:
    """O valor que o leitor de `chave` lê como «não veio»; ``None`` = sem medida."""
    if chave in _SEM_NAO_VEIO:
        return None
    for prefixo, valor in _NAO_VEIO:
        if chave.startswith(prefixo):
            return valor
    return None


def _sha(texto: str) -> str:
    import hashlib

    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _yaml() -> ModuleType | None:
    """O PyYAML, ou ``None`` — o desfazer roda com o `python3` do sistema."""
    try:
        import yaml
    except ImportError:
        return None
    return yaml


def pares_da_camada_do_lutris(
    lar: Path | None = None, pasta_do_ambiente: Path | None = None, *,
    pelo_proton: bool = False,
) -> dict[str, str]:
    """O que o `.yml` de um jogo excluído do Lutris Flatpak precisa cobrir.

    Cada chave que o desfazer tiraria da caixa (:func:`_desfazer_pares`, a mesma
    conta da cópia do Heroic), no valor que o jogo veria sem o Hefesto: o
    «antes» do registro da caixa quando ela tinha um, e quando não tinha, o
    :func:`nao_veio` do leitor — e, nas que dependem do jogo
    (:data:`_NAO_VEIO_POR_JOGO`), o padrão do script do Proton quando o jogo
    abre por ele (``pelo_proton``). Caixa sem o nosso, ou ilegível = ``{}``.
    """
    base, por_jogo = _a_camada_da_caixa(lar, pasta_do_ambiente)
    return _com_o_padrao_do_jogo(base, por_jogo, pelo_proton=pelo_proton)


def _com_o_padrao_do_jogo(base: dict[str, str], por_jogo: frozenset[str], *,
                          pelo_proton: bool) -> dict[str, str]:
    """A camada da caixa com o «não veio» das chaves que dependem do jogo."""
    fora = dict(base)
    if pelo_proton:
        for chave in sorted(por_jogo):
            fora.update(dict(_NAO_VEIO_POR_JOGO[chave]))
    return fora


def _a_camada_da_caixa(
    lar: Path | None, pasta_do_ambiente: Path | None,
) -> tuple[dict[str, str], frozenset[str]]:
    """``(os pares de todo jogo, as chaves nossas da caixa que dependem do jogo)``."""
    lar = Path.home() if lar is None else lar
    caixa = _override_da_caixa(_LUTRIS_APP_ID, lar)
    cfg = _ler_override(caixa)
    if cfg is None or not cfg.has_section("Environment"):
        return {}, frozenset()
    entrada = ler_registro(pasta_do_ambiente).get(str(caixa), Entrada(FLATPAK_OVERRIDE))
    novos, contas = _desfazer_pares(list(cfg.items("Environment")), copy.deepcopy(entrada))
    devolvidos = dict(novos)
    fora: dict[str, str] = {}
    por_jogo: set[str] = set()
    for chave in contas.tiradas:
        if chave in contas.devolvidas and chave in devolvidos:
            fora[chave] = devolvidos[chave]
            continue
        if chave in _NAO_VEIO_POR_JOGO:
            por_jogo.add(chave)
            continue
        valor = None if chave in PODEM_SER_DELA else nao_veio(chave)
        if valor is not None:
            fora[chave] = valor
    return fora, frozenset(por_jogo)


def _pasta_do_lutris_flatpak(lar: Path | None) -> Path | None:
    """A casa do Lutris Flatpak, que o censo acha pela regra do Lutris.

    A regra mora no censo (`censo_dos_lancadores.pasta_do_flatpak`): a cópia
    que morava aqui tentava a `config/` e a `data/` do Flatpak, o censo só a
    `config/`, e as duas respostas divergiam na mesma máquina (02/10/2026).
    """
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    return censo.pasta_do_flatpak("Lutris", lar)


def _pelo_proton_por_yml(lar: Path | None) -> dict[str, bool]:
    """``{.yml do jogo: abre pelo Proton}`` no Lutris Flatpak, pelo censo."""
    pasta = _pasta_do_lutris_flatpak(lar)
    if pasta is None:
        return {}
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    #: O LAR VAI JUNTO (02/10/2026): o censo não o deduz do caminho, e é nele
    #: que acha a pasta de dados e o Proton.
    return {str(j.configuracao): j.pelo_proton for j in censo._lutris(pasta, lar).jogos
            if j.configuracao is not None}


def _dizer_o_par(alvo: Path, par: int) -> None:
    """A linha do diário: o `.yml` deste jogo recebeu (1) ou perdeu (0) o par do xalia."""
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.utils.logging_config import get_logger

        get_logger(__name__).info("camada_do_lutris_xalia", par=par, jogo=alvo.stem)


def jogos_do_lutris_pela_janela(classe: str, lar: Path | None = None) -> list[Path]:
    """Os `.yml` dos jogos do Lutris FLATPAK que anunciam esta janela.

    Quem diz qual jogo anuncia qual janela é o censo (`classe_de_janela`, com o
    umu-id do Lutris); a casa é só a do Flatpak (o nativo não ganha camada).
    Só os `.yml` que existem: sem ele o Lutris nem abre o jogo.
    """
    alvo = classe.strip()
    pasta = _pasta_do_lutris_flatpak(lar)
    if not alvo or pasta is None:
        return []
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    vistos: list[Path] = []
    for jogo in censo._lutris(pasta, lar).jogos:
        yml = jogo.configuracao
        if (jogo.classe_de_janela == alvo and yml is not None and yml.is_file()
                and not yml.is_symlink() and yml not in vistos):
            vistos.append(yml)
    return vistos


def _com_o_nosso_no_yml(
    texto: str, pares: dict[str, str], moldura: tuple[str, ...] = (),
    ja_nossos: tuple[tuple[str, str], ...] = (),
) -> tuple[str, tuple[tuple[str, str], ...], tuple[str, ...]] | None:
    """O `.yml` com os pares em `system.env`, sem passar por cima de chave dela.

    Devolve ``(texto, os pares postos, a moldura)``; ``None`` = o arquivo não é
    um dicionário que o Lutris leria (não se reescreve por cima). Uma chave que
    já está no `system.env` é dela (ou da exclusão, de antes) e fica. O par do
    xalia (:data:`_PAR_DO_XALIA`) entra junto ou não entra: com uma das duas
    posta por ela (fora de ``ja_nossos``), o que é dela manda e o par fica fora.
    """
    yaml = _yaml()
    if yaml is None:
        return None
    try:
        raiz = yaml.safe_load(texto) if texto.strip() else {}
    except yaml.YAMLError:
        return None
    if not isinstance(raiz, dict):
        return None
    nova = list(moldura)
    sistema = raiz.get("system")
    if sistema is None:
        sistema = {}
        nova.append("system")
    if not isinstance(sistema, dict):
        return None
    env = sistema.get("env")
    if env is None:
        env = {}
        nova.append("env")
    if not isinstance(env, dict):
        return None
    nossos = set(ja_nossos)
    if any(k in env and (k, str(env[k])) not in nossos for k in _PAR_DO_XALIA):
        pares = {k: v for k, v in pares.items() if k not in _PAR_DO_XALIA}
    postos = tuple((k, v) for k, v in sorted(pares.items()) if k not in env)
    if not postos:
        return texto, (), moldura
    env.update(dict(postos))
    sistema["env"] = env
    raiz["system"] = sistema
    return (str(yaml.safe_dump(raiz, default_flow_style=False)), postos,
            tuple(dict.fromkeys(nova)))


def _cobrir_no_yml(alvo: Path, pares: dict[str, str]) -> YmlDoJogo | None:
    """Escreve os pares no `.yml` e devolve o registro da volta. ``None`` = erro."""
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        return None
    feito = _com_o_nosso_no_yml(texto, pares)
    if feito is None:
        return None
    novo, postos, moldura = feito
    if novo != texto:
        try:
            _escrever_atomico(alvo, novo)
        except OSError:
            return None
    if _PAR_DO_XALIA & {k for k, _ in postos}:
        _dizer_o_par(alvo, 1)
    return YmlDoJogo(str(alvo), texto, _sha(novo), postos, moldura)


def tirar_o_nosso_do_jogo_do_lutris(
    classe: str, *, lar: Path | None = None, pasta_do_ambiente: Path | None = None,
) -> tuple[tuple[YmlDoJogo, ...], str]:
    """O jogo do Lutris Flatpak com esta janela passa a cobrir a caixa.

    Devolve ``(o que fez, status)``: ``"feito"`` | ``"nada"`` | ``"erro"``. O
    jogo cuja caixa ainda não tem o nosso fica anotado sem pares: a carona o
    cobre quando escrever a caixa. Com erro num `.yml`, os já feitos voltam —
    tudo ou nada. A caixa não é tocada.
    """
    ymls = jogos_do_lutris_pela_janela(classe, lar)
    if not ymls:
        return (), "nada"
    base, por_jogo = _a_camada_da_caixa(lar, pasta_do_ambiente)
    proton = _pelo_proton_por_yml(lar)
    feitos: list[YmlDoJogo] = []
    for alvo in ymls:
        pares = _com_o_padrao_do_jogo(base, por_jogo, pelo_proton=proton.get(str(alvo), False))
        yml = _cobrir_no_yml(alvo, pares)
        if yml is None:
            devolver_ao_jogo_do_lutris(feitos)
            return (), "erro"
        feitos.append(yml)
    return tuple(feitos), "feito" if any(y.pares for y in feitos) else "nada"


def _manter_o_yml(yml: YmlDoJogo, pares: dict[str, str]) -> YmlDoJogo | None:
    """A carona mantém o `.yml` do excluído cobrindo a caixa de agora.

    Acrescenta, e o que falta se lê no ARQUIVO, não no registro: o uninstall
    que guarda a configuração devolve o `.yml` e deixa a entrada, e o install de
    depois deixava o excluído sem a camada (medido em 02/10/2026).
    **O PAR DO XALIA SEGUE O JOGO** (02/10/2026): ele também SAI, quando o jogo
    deixa de abrir pelo Proton (ela trocou o Wine dele) ou o xalia da caixa
    deixa de ser nosso; sai só o par que ainda tem o valor nosso.
    Devolve o registro novo quando escreveu, ``None`` quando não mudou nada ou
    não pôde. Se ela mexeu no arquivo desde a última escrita nossa, a volta
    exata deixa de valer (``antes=None``); o arquivo igual ao «antes» a mantém.
    """
    alvo = Path(yml.arquivo)
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        return None
    if not pares:
        return None
    velhos = tuple((k, v) for k, v in yml.pares if k in _PAR_DO_XALIA and k not in pares)
    base = _sem_os_pares_no_yml(texto, replace(yml, pares=velhos)) if velhos else texto
    if base is None:
        return None
    ja_nossos = tuple(p for p in yml.pares if p not in velhos)
    feito = _com_o_nosso_no_yml(base, pares, yml.moldura, ja_nossos)
    if feito is None:
        return None
    novo, postos, moldura = feito
    if novo == texto:
        return None
    try:
        _escrever_atomico(alvo, novo)
    except OSError:
        return None
    if velhos:
        _dizer_o_par(alvo, 0)
    if _PAR_DO_XALIA & {k for k, _ in postos}:
        _dizer_o_par(alvo, 1)
    antes = yml.antes if _sha(texto) == yml.depois or texto == yml.antes else None
    todos = tuple({**dict(ja_nossos), **dict(postos)}.items())
    return YmlDoJogo(yml.arquivo, antes, _sha(novo), todos, moldura)


def _sem_os_pares_no_yml(texto: str, yml: YmlDoJogo) -> str | None:
    """O `.yml` sem os pares da exclusão que ainda estão lá com o valor dela.

    ``None`` = sem PyYAML, ou o arquivo não abre: não se escreve YAML à mão.
    """
    yaml = _yaml()
    if yaml is None:
        return None
    try:
        raiz = yaml.safe_load(texto)
    except yaml.YAMLError:
        return None
    sistema = raiz.get("system") if isinstance(raiz, dict) else None
    env = sistema.get("env") if isinstance(sistema, dict) else None
    if not isinstance(raiz, dict) or not isinstance(sistema, dict) or not isinstance(env, dict):
        return texto
    for chave, valor in yml.pares:
        if chave in env and env[chave] == valor:
            del env[chave]
    if "env" in yml.moldura and not env:
        del sistema["env"]
    if "system" in yml.moldura and not sistema:
        del raiz["system"]
    return str(yaml.safe_dump(raiz, default_flow_style=False))


def devolver_ao_jogo_do_lutris(ymls: Iterable[YmlDoJogo]) -> str:
    """A volta: o `.yml` de cada jogo como estava antes da exclusão.

    Se ninguém mexeu no arquivo desde a última escrita nossa (o `sha256` bate),
    o texto de antes volta inteiro, byte a byte — sem PyYAML. Se ela (ou o
    Lutris) mexeu, saem só os pares da exclusão que ainda têm o valor dela, e
    isso precisa do PyYAML; sem ele o arquivo fica como está e o status é
    ``"ficou"``. Status: ``"feito"`` | ``"nada"`` | ``"ficou"`` | ``"erro"``.
    Nunca levanta.
    """
    status = "nada"
    for yml in ymls:
        if not yml.pares:
            continue
        alvo = Path(yml.arquivo)
        try:
            texto = alvo.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        except OSError:
            status = "erro"
            continue
        if yml.antes is not None and _sha(texto) == _sha(yml.antes):
            continue  # já voltou: o desfazer adiado roda de novo sobre a lista
        if _sha(texto) == yml.depois and yml.antes is not None:
            novo = yml.antes
        else:
            parcial = _sem_os_pares_no_yml(texto, yml)
            if parcial is None:
                if status != "erro":
                    status = "ficou"
                continue
            novo = parcial
        if novo == texto:
            continue
        try:
            _escrever_atomico(alvo, novo)
        except OSError:
            status = "erro"
            continue
        if status == "nada":
            status = "feito"
    return status


def _manter_os_ymls(ymls: Iterable[YmlDoJogo], lar: Path | None,
                    pasta_do_ambiente: Path | None) -> list[YmlDoJogo]:
    """A carona sobre os `.yml` dos excluídos: os registros que mudaram."""
    lista = list(ymls)
    if not lista:
        return []
    base, por_jogo = _a_camada_da_caixa(lar, pasta_do_ambiente)
    proton = _pelo_proton_por_yml(lar) if por_jogo else {}
    mudados: list[YmlDoJogo] = []
    for yml in lista:
        with contextlib.suppress(Exception):
            pares = _com_o_padrao_do_jogo(
                base, por_jogo, pelo_proton=proton.get(yml.arquivo, False))
            novo = _manter_o_yml(yml, pares)
            if novo is not None:
                mudados.append(novo)
    if mudados:
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx

            lx.anotar_os_ymls(mudados)
    return mudados


def _pastas_do_ambiente_padrao(lar: Path) -> list[Path]:
    """As `launch_env` desta casa pela regra do XDG — e a do lar, se for outra.

    Só biblioteca padrão: é a conta que o `uninstall.sh` também faz.
    """
    from hefesto_dualsense4unix.utils import identidade

    slug = identidade.atual().slug
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    estados = [Path(xdg)] if os.path.isabs(xdg) else []
    estados.append(lar / ".local/state")
    fora: list[Path] = []
    for estado in estados:
        pasta = estado / slug / "launch_env"
        if pasta not in fora:
            fora.append(pasta)
    return fora


def _listas_de_exclusao_padrao(lar: Path) -> list[Path]:
    """A lista de exclusão pela regra do XDG — e a do lar, se for outra."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    casas = [Path(xdg)] if os.path.isabs(xdg) else []
    casas.append(lar / ".config")
    return list(dict.fromkeys(casa / RELPATH_DA_LISTA for casa in casas))


def main(argv: Sequence[str] | None = None) -> int:
    """`--desfazer`: o passo do `uninstall.sh`. Sai 0 completo, 1 com sobra."""
    p = argparse.ArgumentParser(
        prog="cura_por_estrada.py",
        description="Tira dos lançadores (Heroic, overrides do Flatpak) o "
                    "ambiente que o Hefesto escreveu — só o que é dele.")
    p.add_argument("--desfazer", action="store_true", required=True,
                   help="tira o que o Hefesto pôs e devolve o que estava lá")
    p.add_argument("--lar", default=None, help="o lar (padrão: $HOME)")
    p.add_argument("--pasta-do-ambiente", action="append", default=None,
                   help="a pasta launch_env com o registro (repita para as duas)")
    p.add_argument("--lista-de-exclusao", action="append", default=None,
                   help="a lista de exclusão, para devolver antes os jogos excluídos "
                        "(repita para as duas; padrão: a do XDG e a do lar)")
    a = p.parse_args(argv)
    lar = Path(a.lar) if a.lar else Path.home()
    pastas = ([Path(x) for x in a.pasta_do_ambiente] if a.pasta_do_ambiente
              else _pastas_do_ambiente_padrao(lar))
    listas = ([Path(x) for x in a.lista_de_exclusao] if a.lista_de_exclusao
              else _listas_de_exclusao_padrao(lar))
    feitos, completo = desfazer_as_estradas(pastas, lar, listas)
    if completo:
        #: O DESFAZER QUE FICOU PARA DEPOIS deixou a pasta de estado de pé SÓ
        #: pelo registro (o uninstall apagou o resto): terminado ele, ela sai.
        #: Só `rmdir` — uma pasta com qualquer outra coisa dentro fica, e é o
        #: passo dela que a nomeia. No uninstall de uma vez, o `default.env`
        #: ainda está ali e nada sai daqui.
        #:
        #: A LISTA DE EXCLUSÃO QUE O UNINSTALL GUARDOU NO `launch_env` (com o
        #: --purge-config e o desfazer adiado, O-UNINSTALL-DEVOLVE-O-JOGO-EXCLUIDO-01)
        #: só existe para este desfazer: terminado ele, ela sai. A da
        #: configuração nunca sai daqui.
        for lista in listas:
            if lista.parent.name == "launch_env" and lista.name.startswith("lista_de_exclusao"):
                with contextlib.suppress(OSError):
                    lista.unlink()
        for pasta in pastas:
            if pasta.name != "launch_env":
                continue
            for vazia in (pasta, pasta.parent):
                with contextlib.suppress(OSError):
                    vazia.rmdir()
    linhas = [f for f in (frase_do_desfeito(x) for x in feitos) if f]
    for linha in linhas:
        print(linha)
    if not linhas:
        print("nenhum ambiente do Hefesto nos lançadores")
    return 0 if completo else 1


if __name__ == "__main__":  # pragma: no cover - passo do uninstall.sh
    sys.exit(main())
