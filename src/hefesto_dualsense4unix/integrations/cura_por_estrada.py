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
* **nunca escreve fora da allowlist** (`daemon.launch_env.ENV_ALLOWLIST`). O
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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
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

#: A subpasta de configuração do Heroic, dentro do flatpak ou do lar nativo —
#: a mesma que `censo_dos_lancadores._pasta_de_config` acha.
_HEROIC_APP_ID = "com.heroicgameslauncher.hgl"

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

#: AS DUAS QUE UMA PESSOA COSTUMA PÔR SOZINHA — o cache de shader da NVIDIA. É
#: a mesma leitura do «limpa?» (`utils/memoria_dos_controles`, a régua confere
#: que são iguais): o valor que ela tinha antes da primeira escrita do Hefesto
#: é guardado e volta no desfazer.
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

#: As duas casas do Heroic no lar — flatpak primeiro, nativo depois.
_PASTAS_DO_HEROIC = (f".var/app/{_HEROIC_APP_ID}/config/heroic", ".config/heroic")


def _pasta_do_heroic(lar: Path) -> Path | None:
    """A pasta de configuração do Heroic — flatpak primeiro, nativo depois."""
    for rel in _PASTAS_DO_HEROIC:
        tentativa = lar / rel
        if tentativa.is_dir():
            return tentativa
    return None


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
    lar = Path.home() if lar is None else lar
    if chave == "steam":
        return ()
    if chave == "heroic":
        pasta = _pasta_do_heroic(lar)
        if pasta is None:
            return ()
        return (Estrada(chave, HEROIC_CONFIG, pasta / "config.json"),)
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
    ambiente = ambiente_da_ponte(pasta_do_ambiente)
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
            if any(a == chave for a, _ in pares):
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


def _tomar(pares: Pares, ambiente: dict[str, str], entrada: Entrada) -> Pares:
    """A ESCRITA sobre os pares do arquivo, anotando no registro o que é nosso.

    Uma chave nossa que saiu do ambiente sai do arquivo (o Modo Nativo não tem
    `IGNORE`: um `IGNORE` congelado no Heroic deixava o jogo sem o controle
    que o Modo Nativo existe para mostrar). As de agora entram por cima.
    """
    atual = dict(pares)
    pares = _devolver_chaves(
        pares, [k for k in entrada.chaves if k not in ambiente], entrada, _Contas())
    for chave, valor in ambiente.items():
        marca = entrada.chaves.get(chave)
        if marca is None:
            #: A PRIMEIRA VEZ. Só as que podem ser dela guardam o «antes»: as
            #: demais são do produto, e um valor que já estava lá é presumido de
            #: uma versão que escrevia sem registro (ver o cabeçalho).
            antes = atual.get(chave) if chave in PODEM_SER_DELA else None
            entrada.chaves[chave] = Marca([valor], antes)
        elif marca.valores[-1] != valor:
            marca.valores = (
                [v for v in marca.valores if v != valor] + [valor])[-_VALORES_LEMBRADOS:]
    return _por_por_cima(pares, ambiente)


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
    """
    escritos: list[str] = []
    for chave, atalhos in cartoes_com_estrada():
        try:
            plano = planejar(chave, atalhos, lar, pasta_do_ambiente,
                             raiz_sistema)
            if plano.impedimento or not plano.estradas or not plano.ambiente:
                continue
            escrever_a_estrada(plano)
        except Exception:  # pragma: no cover - disco hostil; ver a docstring
            continue
        escritos.append(chave)
    return tuple(escritos)


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


def estradas_possiveis(lar: Path) -> list[tuple[Path, str]]:
    """Todo arquivo de lançador em que a cura pode ter escrito, e que existe.

    É a rede de quem escreveu SEM registro: o `config.json` nas duas casas do
    Heroic, e o override de cada `app-id` dos cartões com estrada — instalado
    ou não, porque desinstalar o lançador pelo Flatpak não leva o override.
    """
    achados: list[tuple[Path, str]] = []
    for rel in _PASTAS_DO_HEROIC:
        alvo = lar / rel / "config.json"
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
    """``[(config.json da casa, cópia de um jogo)]`` nas duas casas do Heroic.

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
    for rel in _PASTAS_DO_HEROIC:
        casa = lar / rel
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
    return Entrada(HEROIC_CONFIG, chaves={
        k: copy.deepcopy(m) for k, m in entrada.chaves.items() if k not in PODEM_SER_DELA})


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


def desfazer_as_estradas(pastas_do_ambiente: Iterable[Path],
                         lar: Path | None = None) -> tuple[list[Desfeito], bool]:
    """Tira de todo lançador o que o Hefesto escreveu. ``(o que fez, completo)``.

    Os arquivos vêm do registro de cada pasta (a do ``XDG_STATE_HOME`` e a do
    lar, quando são duas) e da rede de :func:`estradas_possiveis` — e, depois
    deles, as cópias por jogo que o Heroic tirou da lista global
    (:func:`copias_por_jogo_do_heroic`), lidas com o registro do `config.json`
    da mesma casa. Completo, o registro sai; com um arquivo que não abriu, o
    que é dele fica anotado na primeira pasta, para o desfazer de novo — e a
    resposta é ``False``.
    """
    lar = Path.home() if lar is None else lar
    pastas = list(pastas_do_ambiente)
    registro: dict[str, Entrada] = {}
    for pasta in pastas:
        for caminho, entrada in ler_registro(pasta).items():
            registro.setdefault(caminho, entrada)
    alvos = dict(registro)
    for arquivo, tipo in estradas_possiveis(lar):
        alvos.setdefault(str(arquivo), Entrada(tipo))
    feitos: list[Desfeito] = []
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
    return f"{feito.arquivo}: " + "; ".join(partes) if partes else ""


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
    a = p.parse_args(argv)
    lar = Path(a.lar) if a.lar else Path.home()
    pastas = ([Path(x) for x in a.pasta_do_ambiente] if a.pasta_do_ambiente
              else _pastas_do_ambiente_padrao(lar))
    feitos, completo = desfazer_as_estradas(pastas, lar)
    if completo:
        #: O DESFAZER QUE FICOU PARA DEPOIS deixou a pasta de estado de pé SÓ
        #: pelo registro (o uninstall apagou o resto): terminado ele, ela sai.
        #: Só `rmdir` — uma pasta com qualquer outra coisa dentro fica, e é o
        #: passo dela que a nomeia. No uninstall de uma vez, o `default.env`
        #: ainda está ali e nada sai daqui.
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
