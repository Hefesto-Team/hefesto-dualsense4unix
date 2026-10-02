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
    # `identidade_de_janela`) é só biblioteca padrão.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from hefesto_dualsense4unix.integrations import sandbox_dos_lancadores as _caixa

HEROIC_CONFIG = "heroic-config"
FLATPAK_OVERRIDE = "flatpak-override"

CHAVE_DO_HEROIC = "enviromentOptions"

SEM_AMBIENTE = ("O serviço ainda não publicou o ambiente desta sessão. Ligue o "
                "Hefesto, conecte um controle e tente de novo.")

ILEGIVEL = ("Não consegui ler o `{arquivo}` deste lançador, e não vou "
            "reescrevê-lo por cima. Abra o lançador uma vez e tente de novo.")

PODEM_SER_DELA: frozenset[str] = frozenset(
    {"__GL_SHADER_DISK_CACHE", "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP"})

_DO_PRODUTO_SEM_REGISTRO: frozenset[str] = frozenset({
    "SDL_GAMECONTROLLER_IGNORE_DEVICES",
    "SDL_JOYSTICK_HIDAPI",
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS",
    "PROTON_DISABLE_HIDRAW",
    "SDL_ACCELEROMETER_AS_JOYSTICK",
    "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE",
    "PROTON_ENABLE_MHWILDS_USB_AUDIO",
})

CORRECOES_DA_CARONA: tuple[tuple[str, str], ...] = (("PROTON_USE_XALIA", "0"),)

DELA_MANDA: frozenset[str] = frozenset(k for k, _ in CORRECOES_DA_CARONA)

_VALORES_LEMBRADOS = 16


def _pasta_do_ambiente(pasta: Path | None) -> Path:
    """A pasta `launch_env` — a pedida, ou a do daemon (import tardio)."""
    if pasta is not None:
        return pasta
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    return launch_env_dir()


def ambiente_da_ponte(pasta: Path | None = None) -> dict[str, str]:
    """O ambiente que o daemon publicou para ESTA sessão — ou `{}`."""
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
    """O que a carona leva a cada estrada: a ponte e as :data:`CORRECOES_DA_CARONA`."""
    ponte = ambiente_da_ponte(pasta)
    return {**ponte, **dict(CORRECOES_DA_CARONA)} if ponte else {}


@dataclass(frozen=True)
class Estrada:
    """Por onde o ambiente entra NESTE lançador."""

    cartao: str
    tipo: str
    arquivo: Path
    app_id: str = ""


@dataclass(frozen=True)
class Plano:
    """O que a cura FARIA, antes de fazer."""

    cartao: str
    estradas: tuple[Estrada, ...] = ()
    ambiente: dict[str, str] = field(default_factory=dict)
    impedimento: str = ""
    nome: str = ""
    pasta_do_ambiente: Path | None = None

    @property
    def rotulo(self) -> str:
        """O que a TELA chama este cartão. A chave interna é a queda."""
        return self.nome or self.cartao


_PASTA_DOS_OVERRIDES = ".local/share/flatpak/overrides"

def _pastas_do_heroic(lar: Path | None) -> tuple[Path, ...]:
    """As casas do Heroic em que a carona escreve: as que o censo lê."""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    return censo.pastas_lidas("Heroic", lar)


def _pasta_do_heroic(lar: Path | None) -> Path | None:
    """A primeira casa do Heroic que o censo lê (a do Flatpak, quando são duas)."""
    pastas = _pastas_do_heroic(lar)
    return pastas[0] if pastas else None


def estradas_do_cartao(chave: str, atalhos: tuple[str, ...],
                       lar: Path | None = None,
                       raiz_sistema: Path | None = None) -> tuple[Estrada, ...]:
    """Por onde a cura entra neste cartão. Vazio = não há estrada aqui."""
    if chave == "steam":
        return ()
    if chave == "heroic":
        return tuple(Estrada(chave, HEROIC_CONFIG, pasta / "config.json")
                     for pasta in _pastas_do_heroic(lar))
    lar = Path.home() if lar is None else lar
    raiz = lar / _PASTA_DOS_OVERRIDES
    return tuple(Estrada(chave, FLATPAK_OVERRIDE, raiz / a, a)
                 for a in _caixa.app_ids_instalados(atalhos, lar, raiz_sistema))


def planejar(chave: str, atalhos: tuple[str, ...], lar: Path | None = None,
             pasta_do_ambiente: Path | None = None,
             raiz_sistema: Path | None = None, nome: str = "") -> Plano:
    """O que a cura faria neste cartão — sem escrever um byte."""
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
    """Há botão a oferecer neste cartão? — a pergunta da VIGIA."""
    return bool(estradas_do_cartao(chave, atalhos, lar, raiz_sistema))


def _modo_de_nascimento(pasta: Path) -> int:
    """O modo de um arquivo que NASCE nesta pasta — herdado dela."""
    try:
        return stat.S_IMODE(pasta.stat().st_mode) & 0o666
    except OSError:  # pragma: no cover - a pasta acabou de ser criada
        return 0o644


def _escrever_atomico(alvo: Path, texto: str) -> None:
    """Grava por arquivo temporário no MESMO diretório, e então renomeia."""
    alvo.parent.mkdir(parents=True, exist_ok=True)
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
    """O `config.json` do Heroic, `{}` se ele não existe, `None` se ILEGÍVEL."""
    if not alvo.exists():
        return {}
    try:
        dado = cast("object", json.loads(alvo.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None
    return dado if isinstance(dado, dict) else None


@dataclass
class Marca:
    """Uma chave nossa num arquivo dela."""

    valores: list[str]
    antes: str | None = None


@dataclass
class Entrada:
    """O que o Hefesto pôs num arquivo de lançador."""

    tipo: str
    nasceu: bool = False
    moldura: list[str] = field(default_factory=list)
    chaves: dict[str, Marca] = field(default_factory=dict)


Pares = list[tuple[str, str]]


def caminho_do_registro(pasta_do_ambiente: Path | None = None) -> Path:
    """O registro mora AO LADO do `default.env`, dentro do `launch_env/`."""
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
    """A entrada que a escrita atualiza — nova quando o arquivo não existe."""
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
    """As nossas no lugar em que já estavam; as que faltam, no fim, em ordem."""
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
    """Tira as chaves nossas pedidas — só onde o valor ainda é NOSSO."""
    for chave in list(chaves):
        marca = entrada.chaves.pop(chave)
        nossos = set(marca.valores)
        if not any(a == chave and b in nossos for a, b in pares):
            if any(a == chave and not (chave in DELA_MANDA and b == marca.antes)
                   for a, b in pares):
                contas.ficaram.append(chave)
            continue
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
    """As :data:`DELA_MANDA` do ambiente que ela já pôs neste arquivo."""
    dela: set[str] = set()
    for chave in DELA_MANDA & ambiente.keys():
        marca = entrada.chaves.get(chave)
        nossos = set(marca.valores) if marca is not None else set()
        if any(a == chave and b not in nossos for a, b in pares):
            dela.add(chave)
    return frozenset(dela)


def _tomar(pares: Pares, ambiente: dict[str, str], entrada: Entrada) -> Pares:
    """A ESCRITA sobre os pares do arquivo, anotando no registro o que é nosso."""
    dela = _as_que_ela_pos(pares, ambiente, entrada)
    atual = dict(pares)
    pares = _devolver_chaves(
        pares, [k for k in entrada.chaves if k not in ambiente], entrada, _Contas())
    for chave, valor in ambiente.items():
        marca = entrada.chaves.get(chave)
        if marca is None:
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
    """O `config.json` do Heroic com o ambiente fundido, e o registro dele."""
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
    """Funde o ambiente em `defaultSettings.enviromentOptions` e grava."""
    texto, nova = _heroic_fundido(alvo, ambiente, entrada)
    _escrever_atomico(alvo, texto)
    return nova


def _render_ini(cfg: configparser.ConfigParser) -> str:
    """O arquivo de override como o Flatpak o escreve — `chave=valor`, sem espaço."""
    partes: list[str] = []
    for secao in cfg.sections():
        partes.append(f"[{secao}]")
        partes += [f"{k}={v}" for k, v in cfg.items(secao)]
        partes.append("")
    return "\n".join(partes).rstrip("\n") + "\n"


def _ler_override(alvo: Path) -> configparser.ConfigParser | None:
    """O override deste aplicativo, vazio se não existe, `None` se ILEGÍVEL."""
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
    """Põe o ambiente em `[Environment]`, preservando todo o resto do arquivo."""
    texto, nova = _override_fundido(alvo, ambiente, entrada)
    _escrever_atomico(alvo, texto)
    return nova


def frase_do_feito(plano: Plano) -> str:
    """O recibo que a tela mostra — e ele diz o que mudou, onde e o que fazer."""
    n = len(plano.ambiente)
    k = len(plano.estradas)
    quantos = f"os {k} programas " if k > 1 else ""
    cada = " em cada" if k > 1 else ""
    return (f"{plano.rotulo}: ajustei {quantos}para o jogo enxergar o controle "
            f"pelo Hefesto — {n} {'ajuste' if n == 1 else 'ajustes'}{cada}. "
            "Feche e abra o lançador para valer.")


def escrever_a_estrada(plano: Plano) -> str:
    """Escreve o ambiente nas estradas do plano e diz o que escreveu."""
    if plano.impedimento:
        raise RuntimeError(plano.impedimento)
    if not plano.estradas:
        raise RuntimeError("não há por onde entrar neste lançador")
    if not plano.ambiente:
        raise RuntimeError(SEM_AMBIENTE)
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
    if registro != lido:
        gravar_registro(registro, plano.pasta_do_ambiente)
    for alvo, texto in textos:
        _escrever_atomico(alvo, texto)
    return frase_do_feito(plano)


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
    """Escreve o ambiente da ponte em TODA estrada que existir. O que escreveu."""
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
    _manter_os_ymls(fora.ymls, lar, pasta_do_ambiente)
    return tuple(escritos)


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
    """O ambiente de agora em cada cópia com lista própria desta casa."""
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
    """O recibo da carona, para o diário: os lançadores que receberam o ambiente."""
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
    """Onde o ambiente de agora NÃO está neste cartão — para a aba Lançadores."""
    plano = planejar(chave, atalhos, lar, pasta_do_ambiente, raiz_sistema)
    if plano.impedimento or not plano.estradas or not plano.ambiente:
        return ()
    fora = _a_exclusao() if exclusao is None else exclusao

    def falta_em(pares: Pares, ambiente: dict[str, str]) -> bool:
        tem = dict(pares)
        return any(tem.get(k) != v and not (k in DELA_MANDA and k in tem)
                   for k, v in ambiente.items())

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


@dataclass
class Desfeito:
    """O que o desfazer fez num arquivo de lançador."""

    arquivo: Path
    tiradas: list[str] = field(default_factory=list)
    devolvidas: list[str] = field(default_factory=list)
    ficaram: list[str] = field(default_factory=list)
    apagado: bool = False
    erro: str = ""
    voltou: bool = False


def _casas_do_heroic_na_rede(lar: Path) -> list[Path]:
    """Toda casa do Heroic que existe, instalado ou não — a rede do desfazer."""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    casas = list(censo.pastas_que_existem("Heroic", lar))
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if os.path.isabs(xdg):
        for casa in censo.pastas_que_existem("Heroic", lar, xdg_config=Path(xdg)):
            if casa not in casas:
                casas.append(casa)
    return casas


def estradas_possiveis(lar: Path) -> list[tuple[Path, str]]:
    """Todo arquivo de lançador em que a cura pode ter escrito, e que existe."""
    achados: list[tuple[Path, str]] = []
    for casa in _casas_do_heroic_na_rede(lar):
        alvo = casa / "config.json"
        if alvo.is_file():
            achados.append((alvo, HEROIC_CONFIG))
    raiz = lar / _PASTA_DOS_OVERRIDES
    for chave, atalhos in cartoes_com_estrada():
        if chave == "heroic":
            continue
        for app_id in atalhos:
            alvo = raiz / app_id
            if "." in app_id and alvo.is_file():
                achados.append((alvo, FLATPAK_OVERRIDE))
    return achados


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
    """O registro do `config.json` da casa, como vale para a cópia de um jogo."""
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
    """A cópia de um jogo sem o que é nosso; ``None`` = igual (ou não é para mexer)."""
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


RELPATH_DA_LISTA = "hefesto-dualsense4unix/lista_de_exclusao.json"


def caminho_da_lista(config_home: Path | None = None) -> Path:
    """``$XDG_CONFIG_HOME/hefesto-dualsense4unix/lista_de_exclusao.json``."""
    if config_home is None:
        xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
        config_home = Path(xdg) if xdg else Path.home() / ".config"
    return config_home / RELPATH_DA_LISTA


NOME_DA_TRAVA = ".lista_de_exclusao.trava"

ESPERA_DA_JANELA_S = 5.0

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
    """O filho de um `fork` nasce sem trava: o descritor herdado só se fecha."""
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
    """O descritor com o `flock` exclusivo; ``-1`` = segue sem; ``None`` = o prazo passou."""
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
    """Espera o `flock` na fila do núcleo, com prazo; ``fd`` / ``-1`` / ``None``."""
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
    """Solta o `flock` e fecha. O `LOCK_UN` vem antes: um filho de `fork` que"""
    with contextlib.suppress(OSError, ImportError):
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)
    with contextlib.suppress(OSError):
        os.close(fd)


@contextlib.contextmanager
def trava_da_lista(lista: Path | None = None, *, espera: float | None = None,
                   criar: bool = True) -> Iterator[bool]:
    """Um escritor por vez na lista de exclusão e no que ela anota."""
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
    """As cópias do Heroic e os `.yml` do Lutris que a lista anotou, lida como JSON cru."""
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
    """A cópia que a exclusão CRIOU da lista global perde o cache de shader nosso."""
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
    """A volta de cada jogo excluído fora da Steam, antes de tirar o nosso."""
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
    """Tira de todo lançador o que o Hefesto escreveu. ``(o que fez, completo)``."""
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


@dataclass(frozen=True)
class CopiaDoJogo:
    """O que a exclusão fez na cópia de UM jogo do Heroic — e como voltar."""

    arquivo: str
    app: str
    nasceu: bool = False
    sem_jogo: bool = False
    sem_lista: bool = False
    antes: tuple[tuple[str, str], ...] = ()
    depois: tuple[tuple[str, str], ...] = ()
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
    """O que a exclusão fez no `.yml` de UM jogo do Lutris Flatpak — e como voltar."""

    arquivo: str
    antes: str | None
    depois: str
    pares: tuple[tuple[str, str], ...] = ()
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

    caixas: frozenset[str] = frozenset()
    copias: tuple[CopiaDoJogo, ...] = ()
    ymls: tuple[YmlDoJogo, ...] = ()


def _a_exclusao() -> NaExclusao:
    """A lista do dono (`lista_de_exclusao`), lida tarde. Nunca levanta."""
    try:
        from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx

        return lx.o_que_a_carona_pula()
    except Exception:
        return NaExclusao()


def _sem_o_nosso_no_jogo(
    alvo: Path, app: str, pasta_do_ambiente: Path | None = None,
) -> tuple[str, CopiaDoJogo | None]:
    """A cópia do jogo `app` com a lista própria, sem nada do que é nosso."""
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
        raiz.setdefault("version", "v0")
        raiz.setdefault("explicit", True)
    try:
        _escrever_atomico(alvo, json.dumps(raiz, indent=2, ensure_ascii=False))
    except OSError:
        return "erro", None
    return "feito", copia


def jogos_do_heroic_pela_janela(classe: str, lar: Path | None = None) -> list[Path]:
    """As cópias (`GamesConfig/<app>.json`) dos jogos do Heroic com esta janela."""
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
    """O jogo do Heroic com esta janela passa a ter a lista própria sem o nosso."""
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
    """A volta: a cópia de cada jogo como estava antes da exclusão."""
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
    """A caixa do Flatpak destes `app-id` sem o ambiente que é nosso."""
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


_LUTRIS_APP_ID = "net.lutris.Lutris"

_NAO_VEIO: tuple[tuple[str, str], ...] = (("SDL_", ""), ("PROTON_", ""))

_NAO_VEIO_POR_JOGO: dict[str, tuple[tuple[str, str], ...]] = {
    "PROTON_USE_XALIA": (("PROTON_USE_XALIA", "1"), ("XALIA_SUPPORTED_ONLY", "1")),
}

_SEM_NAO_VEIO: frozenset[str] = frozenset(_NAO_VEIO_POR_JOGO)

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
    """A casa do Lutris Flatpak, que o censo acha pela regra do Lutris."""
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    return censo.pasta_do_flatpak("Lutris", lar)


def _pelo_proton_por_yml(lar: Path | None) -> dict[str, bool]:
    """``{.yml do jogo: abre pelo Proton}`` no Lutris Flatpak, pelo censo."""
    pasta = _pasta_do_lutris_flatpak(lar)
    if pasta is None:
        return {}
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    return {str(j.configuracao): j.pelo_proton for j in censo._lutris(pasta, lar).jogos
            if j.configuracao is not None}


def _dizer_o_par(alvo: Path, par: int) -> None:
    """A linha do diário: o `.yml` deste jogo recebeu (1) ou perdeu (0) o par do xalia."""
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.utils.logging_config import get_logger

        get_logger(__name__).info("camada_do_lutris_xalia", par=par, jogo=alvo.stem)


def jogos_do_lutris_pela_janela(classe: str, lar: Path | None = None) -> list[Path]:
    """Os `.yml` dos jogos do Lutris FLATPAK que anunciam esta janela."""
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
    """O `.yml` com os pares em `system.env`, sem passar por cima de chave dela."""
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
    """O jogo do Lutris Flatpak com esta janela passa a cobrir a caixa."""
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
    """A carona mantém o `.yml` do excluído cobrindo a caixa de agora."""
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
    """O `.yml` sem os pares da exclusão que ainda estão lá com o valor dela."""
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
    """A volta: o `.yml` de cada jogo como estava antes da exclusão."""
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
            continue
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
    """As `launch_env` desta casa pela regra do XDG — e a do lar, se for outra."""
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
