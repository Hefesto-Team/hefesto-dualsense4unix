"""PRONTUARIO-01 — o que o DISCO sabe sobre cada jogo, e o que ele NÃO sabe.

O alvo que ela nomeou em 15/08/2026, ao sair: *"espero de fato que tenhamos
tudo resolvido e cada um dos jogos locais jogável via cabo ou bt"*. Este módulo
é a régua desse alvo — e a primeira coisa que ele faz é recusar o número fácil.

O QUE ELE NUNCA DIZ
-------------------
**"Este jogo funciona."** O disco não sabe disso, e fingir que sabe seria
repetir o defeito mais caro daqui. Medido em 16/08/2026: `Duskfade` e
`DON'T SCREAM` têm a MESMA assinatura no disco — mesmo motor, mesmas famílias
de API (`rawinput`, `xinput` por `LoadLibrary`), mesmo wrapper na linha, mesmo
Steam Input desligado — e um funciona e o outro não. Qualquer prontuário que
pintasse os dois de verde estaria certo sobre um e errado sobre o outro, sem
maneira de saber qual.

Por isso o veredito é **impedimento**, não aprovação:

- ``IMPEDIDO`` — há um estorvo NOMEADO, com a cura ao lado;
- ``SEM_IMPEDIMENTO_CONHECIDO`` — nada que este módulo saiba detectar. Não é
  promessa de que vai funcionar; é a ausência de motivo conhecido para não;
- ``NAO_SEI`` — o disco não deixou ler (pasta ausente, executável ilegível).

É a mesma disciplina do `WRAPPER-EM-TODOS-01`, o portão que passou a noite
verde com o Pragmata quebrado por contar jogos em vez de nomear o que faltava:
**um censo que só conta mente na direção mais cara, a de parecer completo.**

O QUE ELE DIZ, E ISSO É NOVO
-----------------------------
O cruzamento que faltava. Cada peça já existia sozinha — a linha de
inicialização (`sentinela_do_wrapper`), a API de entrada do executável
(`api_de_entrada`), o Steam Input e a allowlist (`steam_launch_options`) — e
ninguém as tinha posto lado a lado por jogo. Posto lado a lado, o censo da
máquina dela (24 jogos instalados, 16/08/2026) mostra o número que decide o
alvo dela:

    entende_dualsense   7 jogos   SDL ou o plugin DualShock no binário
    indeciso           15 jogos   XInput e mais nada — o vpad só chega por espelho
    sem_evidencia       2 jogos   nenhuma agulha, ou executável ilegível

Quinze dos vinte e quatro dependem de que alguém faça o espelho XInput do nosso
vpad `054c:0df2`. Isso não é detalhe de um jogo: é a maioria da biblioteca.

QUEM O CHAMA, E O QUE ELE ESCREVE
---------------------------------
100% stdlib, para rodar no `python3` do sistema sem venv. Mas ele é módulo de
BANCADA: medido em 21/08/2026, NENHUM chamador em produção o invoca — nem o
`doctor.sh`, nem a janela. `grep -rn prontuario_dos_jogos src scripts
install.sh uninstall.sh assets` devolve só menções em prosa (`schema.py:646`,
`ponte_escada.py:125`, `steam_input_ponte.py:5`, `hotkey.py:481`). Quem o roda
é gente, por `python -m
hefesto_dualsense4unix.integrations.prontuario_dos_jogos`, e a suíte — e a
suíte verde não é chamador: é capacidade sem quem a use.

E ele ESCREVE. O censo é read-only; o `--curar` não é. Desde 19/08/2026,
`curar_o_que_e_automatico` despacha, pela tabela `_CURAS`,
`_curar_excecao_inerte` (grava `UseSteamControllerConfig`) e
`_curar_sem_wrapper` (repõe o `hefesto-launch` nas `LaunchOptions`) — os dois
no `localconfig.vdf` da Steam, com backup ao lado e `tmp`+`replace`. Quem quiser
rodar à vontade usa `--dry-run`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .api_de_entrada import Evidencia, Veredito, examinar_pasta
    from .steam_input_ponte import (
        PONTE_LIGADA,
        PONTE_NADA,
        arvore_viva,
        conferir_reguas,
        garantir_ponte,
        ler_arvores,
    )
    from .steam_launch_options import (
        _PAR_ACF,
        WRAPPER_PREFIX,
        _desescapar_acf,
        discover_vdfs,
        has_extended_ignore,
        is_sandboxed_layout,
        parse_steam_input_allowlist,
        pastas_steamapps,
        read_apps_by_appid,
        steam_input_allowlist_path,
    )
except ImportError:  # pragma: no cover - executado como script avulso
    from api_de_entrada import Evidencia, Veredito, examinar_pasta  # type: ignore[no-redef]
    from steam_input_ponte import (  # type: ignore[no-redef]
        PONTE_LIGADA,
        PONTE_NADA,
        arvore_viva,
        conferir_reguas,
        garantir_ponte,
        ler_arvores,
    )
    from steam_launch_options import (  # type: ignore[no-redef]
        _PAR_ACF,
        WRAPPER_PREFIX,
        _desescapar_acf,
        discover_vdfs,
        has_extended_ignore,
        is_sandboxed_layout,
        parse_steam_input_allowlist,
        pastas_steamapps,
        read_apps_by_appid,
        steam_input_allowlist_path,
    )

IMPEDIDO = "impedido"
SEM_IMPEDIMENTO = "sem_impedimento_conhecido"
NAO_SEI = "nao_sei"

PONTE_CONFIRMADA = "ponte_confirmada"

SEM_WRAPPER = "sem_wrapper"
LINHA_INTOCAVEL = "linha_intocavel"
SEM_EXECUTAVEL = "sem_executavel"
EXCECAO_INERTE = "excecao_inerte"
PONTE_DIVERGENTE = "ponte_divergente"

_ESTORVOS: dict[str, tuple[str, str, bool]] = {
    SEM_WRAPPER: (
        "A linha de Opções de Inicialização não chama o hefesto-launch, "
        "então o jogo nunca lê a máscara e vale a lista da Steam — que manda "
        "ignorar o nosso controle virtual.",
        "O Hefesto repõe sozinho: ao salvar ou aplicar um perfil, e também "
        "assim que a Steam fechar (é o único instante em que a reposição "
        "sobrevive — com ela viva, regrava o arquivo ao sair e engole).",
        True,
    ),
    LINHA_INTOCAVEL: (
        "A linha tem uma lista de dispositivos ignorados numa forma que eu não "
        "sei desmontar sem risco de quebrar o que está lá.",
        "O Hefesto repõe sozinho: ao salvar ou aplicar um perfil, e também "
        "assim que a Steam fechar (é o único instante em que a reposição "
        "sobrevive — com ela viva, regrava o arquivo ao sair e engole).",
        True,
    ),
    SEM_EXECUTAVEL: (
        "Não foi possível ler nenhum executável na pasta do jogo, então não dá "
        "para saber que API de entrada ele usa.",
        "Nenhuma — é cegueira do instrumento, não defeito do jogo.",
        False,
    ),
    EXCECAO_INERTE: (
        "Este jogo está na sua lista de exceções do Steam Input, mas o Steam "
        "Input está DESLIGADO para ele — a exceção não está fazendo nada.",
        "O Hefesto liga sozinho: escreve o UseSteamControllerConfig do jogo "
        "assim que a Steam fechar (é o único instante em que a escrita "
        "sobrevive — com ela viva, a Steam regrava o arquivo ao sair e "
        "engole).",
        True,
    ),
    PONTE_DIVERGENTE: (
        "A ponte que já foi CONFIRMADA neste jogo não é a que está de pé hoje: "
        "uma das duas usa o Steam Input e a outra não. O jogo está recebendo o "
        "controle por um caminho diferente do que funcionou.",
        "A decisão é sua, e são duas: repor a ponte confirmada (devolver o jogo "
        "à sua lista de exceções, ou tirá-lo dela), ou confirmar a ponte de "
        "hoje, se foi você que mudou de ideia. O Hefesto NÃO desfaz gesto seu "
        "na lista — foi você que mexeu nela por último.",
        False,
    ),
}

#: `UseSteamControllerConfig` mora no bloco do jogo, dentro da árvore `apps`
_PS_SUPPORT_GLOBAL = "steamcontroller_pssupport"

_SO_CHAVE_RE = re.compile(r'^\s*"([^"]+)"\s*$')

_INFRAESTRUTURA_RE = re.compile(
    r"^(proton\b|steam linux runtime|steamworks common|steam controller configs)",
    re.IGNORECASE,
)


_PERFIS_RELPATH = "hefesto-dualsense4unix/profiles"

_STEAM_APP_WC_RE = re.compile(r"^steam_app_(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class Ponte:
    """A ponte CONFIRMADA de um jogo, como o disco a guarda."""

    kind: str
    gamepad_flavor: str | None = None
    steam_input: bool = False
    confirmada_em: str | None = None
    confirmada_por: str | None = None

    def como_dicionario(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "gamepad_flavor": self.gamepad_flavor,
            "steam_input": self.steam_input,
            "confirmada_em": self.confirmada_em,
            "confirmada_por": self.confirmada_por,
        }


def pasta_de_perfis(config_home: Path | None = None) -> Path:
    """Onde os perfis moram, sem tocar no disco (gêmea da allowlist)."""
    if config_home is not None:
        base = config_home
    else:
        env = os.environ.get("XDG_CONFIG_HOME")
        base = Path(env) if env else Path.home() / ".config"
    return base / _PERFIS_RELPATH


def pontes_confirmadas(config_home: Path | None = None) -> dict[str, Ponte]:
    """`{appid: Ponte}` de tudo que já foi confirmado nos perfis do disco."""
    pasta = pasta_de_perfis(config_home)
    try:
        arquivos = sorted(pasta.glob("*.json"))
    except OSError:  # pragma: no cover - pasta sumiu entre o listar e o ler
        return {}
    melhor: dict[str, tuple[int, str, Ponte]] = {}
    for arquivo in arquivos:
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(dados, dict):
            continue
        crua = dados.get("ponte")
        if not isinstance(crua, dict) or not isinstance(crua.get("kind"), str):
            continue
        ponte = Ponte(
            kind=str(crua.get("kind")),
            gamepad_flavor=(
                str(crua["gamepad_flavor"])
                if isinstance(crua.get("gamepad_flavor"), str)
                else None
            ),
            steam_input=bool(crua.get("steam_input")),
            confirmada_em=(
                str(crua["confirmada_em"])
                if isinstance(crua.get("confirmada_em"), str)
                else None
            ),
            confirmada_por=(
                str(crua["confirmada_por"])
                if isinstance(crua.get("confirmada_por"), str)
                else None
            ),
        )
        prioridade = dados.get("priority")
        peso = (
            prioridade
            if isinstance(prioridade, int) and not isinstance(prioridade, bool)
            else 0
        )
        nome = dados.get("name") if isinstance(dados.get("name"), str) else arquivo.stem
        for appid in _appids_do_perfil(dados):
            atual = melhor.get(appid)
            if atual is None or (peso, str(nome)) > (atual[0], atual[1]):
                melhor[appid] = (peso, str(nome), ponte)
    return {appid: item[2] for appid, item in melhor.items()}


def classes_com_ponte(config_home: Path | None = None) -> set[str]:
    """As classes de janela (em `casefold`) dos perfis COM ponte confirmada."""
    pasta = pasta_de_perfis(config_home)
    try:
        arquivos = sorted(pasta.glob("*.json"))
    except OSError:  # pragma: no cover - pasta sumiu entre o listar e o ler
        return set()
    achadas: set[str] = set()
    for arquivo in arquivos:
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(dados, dict):
            continue
        crua = dados.get("ponte")
        if not isinstance(crua, dict) or not isinstance(crua.get("kind"), str):
            continue
        match = dados.get("match")
        if not isinstance(match, dict) or match.get("type") != "criteria":
            continue
        classes = match.get("window_class")
        if isinstance(classes, list):
            achadas |= {c.strip().casefold() for c in classes
                        if isinstance(c, str) and c.strip()}
    return achadas


def _appids_do_perfil(dados: dict[str, object]) -> set[str]:
    """Os appids que o `match` deste perfil declara (gêmeo do manager)."""
    match = dados.get("match")
    if not isinstance(match, dict) or match.get("type") != "criteria":
        return set()
    classes = match.get("window_class")
    if not isinstance(classes, list):
        return set()
    achados: set[str] = set()
    for item in classes:
        if not isinstance(item, str):
            continue
        casou = _STEAM_APP_WC_RE.match(item.strip())
        if casou is not None:
            achados.add(casou.group(1))
    return achados


@dataclass(frozen=True)
class Estorvo:
    """Um impedimento nomeado, e o que fazer com ele."""

    chave: str

    @property
    def o_que(self) -> str:
        return _ESTORVOS[self.chave][0]

    @property
    def a_cura(self) -> str:
        return _ESTORVOS[self.chave][1]

    @property
    def automatica(self) -> bool:
        """O produto conserta sozinho, sem ela clicar em nada?"""
        return _ESTORVOS[self.chave][2]


@dataclass(frozen=True)
class Prontuario:
    """A ficha de UM jogo: fatos lidos do disco, e o veredito por último."""

    appid: str
    nome: str
    raiz: Path | None = None
    linha: str | None = None
    evidencia: Evidencia | None = None
    #: `UseSteamControllerConfig` do bloco do jogo. `None` = herda o global.
    steam_input: str | None = None
    steam_input_global: str | None = None
    na_allowlist: bool = False
    ponte: Ponte | None = None


    @property
    def tem_wrapper(self) -> bool:
        return bool(self.linha) and WRAPPER_PREFIX in (self.linha or "")

    @property
    def linha_intocavel(self) -> bool:
        """A linha carrega o nosso par numa forma que o reparo não desmonta."""
        return has_extended_ignore(self.linha or "")

    @property
    def steam_input_ligado(self) -> bool | None:
        """True/False, ou `None` quando nem o jogo nem o global se pronunciam."""
        valor = self.steam_input if self.steam_input is not None else self.steam_input_global
        if valor is None:
            return None
        return valor.strip() != "0"

    @property
    def api(self) -> Veredito:
        return self.evidencia.veredito if self.evidencia else Veredito.SEM_EVIDENCIA

    @property
    def depende_de_espelho(self) -> bool:
        """O vpad só chega a este jogo por um espelho XInput?"""
        return self.api is Veredito.INDECISO

    @property
    def ponte_confirmada(self) -> bool:
        """Alguém já confirmou uma ponte NESTE jogo?"""
        return self.ponte is not None

    @property
    def ponte_divergente(self) -> bool:
        """A ponte de hoje contradiz a que foi confirmada?"""
        return self.ponte is not None and bool(self.ponte.steam_input) != self.na_allowlist

    @property
    def estorvos(self) -> list[Estorvo]:
        """Tudo que o disco consegue nomear como impedimento, em ordem de peso."""
        achados: list[Estorvo] = []
        if not self.tem_wrapper:
            achados.append(Estorvo(LINHA_INTOCAVEL if self.linha_intocavel else SEM_WRAPPER))
        if self.na_allowlist and self.steam_input_ligado is False:
            achados.append(Estorvo(EXCECAO_INERTE))
        if self.raiz is not None and (self.evidencia is None or not self.evidencia.executavel):
            achados.append(Estorvo(SEM_EXECUTAVEL))
        if self.ponte_divergente:
            achados.append(Estorvo(PONTE_DIVERGENTE))
        return achados

    @property
    def veredito(self) -> str:
        """O veredito, com a ponte confirmada DENTRO dele — e nada afrouxado.

        PONTE-CONFIRMADA-01 (19/08/2026). O carimbo entra pelos dois lados que
        ele de fato sustenta, e por nenhum terceiro:

        - contra o jogo, quando a ponte de hoje CONTRADIZ a confirmada: isso é
          um impedimento nomeado, com a cura ao lado, como qualquer outro;
        - a favor, num balde PRÓPRIO: `PONTE_CONFIRMADA`, que diz "esta
          combinação já pegou aqui" — um fato de natureza diferente de tudo o
          mais neste módulo, porque não foi lido do disco: foi confirmado com o
          jogo aberto, na máquina dela.

        O que ele NÃO faz, e a recusa é decisão medida (16/08, Duskfade x
        DON'T SCREAM): promover ninguém a "funciona". `SEM_IMPEDIMENTO`
        continua sendo `sem_impedimento_conhecido` e continua NÃO sendo
        promessa; e o balde da ponte confirmada vale para UMA combinação, a
        carimbada — trocar a máscara ou a lista devolve o jogo à divergência,
        que é o primeiro item aqui em cima. Um carimbo NÃO apaga estorvo: um
        jogo com ponte confirmada e sem wrapper continua `IMPEDIDO`, porque a
        ponte que funcionou não está de pé.

        A ORDEM entre o carimbo e o `NAO_SEI` tem razão, e ela é a varredura
        rápida: com `examinar=False` (o censo que a cura e o portão usam) a
        `evidencia` é `None` para TODOS os jogos, e todo jogo cairia em
        `NAO_SEI` — o carimbo sumiria justo no caminho mais rodado. O carimbo
        não depende de ler executável nenhum, então ele vem antes. O que ele
        NÃO atravessa é a pasta ausente (`raiz is None`): jogo cuja instalação
        sumiu do disco continua `NAO_SEI`, porque aí a cegueira é sobre o jogo
        inteiro, não sobre a API dele.
        """
        if self.estorvos:
            return IMPEDIDO
        if self.ponte_confirmada and self.raiz is not None:
            return PONTE_CONFIRMADA
        if self.raiz is None or self.evidencia is None:
            return NAO_SEI
        return SEM_IMPEDIMENTO

    def como_dicionario(self) -> dict[str, object]:
        """Forma JSON — a saída de `--json`, hoje sem consumidor em produção."""
        return {
            "appid": self.appid,
            "nome": self.nome,
            "veredito": self.veredito,
            "tem_wrapper": self.tem_wrapper,
            "api": self.api.value,
            "depende_de_espelho": self.depende_de_espelho,
            "steam_input_ligado": self.steam_input_ligado,
            "na_allowlist": self.na_allowlist,
            "ponte": self.ponte.como_dicionario() if self.ponte else None,
            "ponte_divergente": self.ponte_divergente,
            "estorvos": [
                {"chave": e.chave, "o_que": e.o_que, "cura": e.a_cura,
                 "automatica": e.automatica}  # (noqa-acento): chave de JSON
                for e in self.estorvos
            ],
        }


@dataclass(frozen=True)
class Censo:
    """Os prontuários de todos os jogos instalados, e o que o conjunto diz."""

    jogos: list[Prontuario] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

    @property
    def impedidos(self) -> list[Prontuario]:
        return [j for j in self.jogos if j.veredito == IMPEDIDO]

    @property
    def curaveis_sozinho(self) -> list[Prontuario]:
        """Impedidos cuja cura o produto aplica sem ela clicar em nada."""
        return [j for j in self.impedidos if all(e.automatica for e in j.estorvos)]

    @property
    def dependem_de_espelho(self) -> list[Prontuario]:
        return [j for j in self.jogos if j.depende_de_espelho]

    @property
    def com_ponte_confirmada(self) -> list[Prontuario]:
        """Os jogos em que alguém já confirmou uma ponte — carimbo, não palpite."""
        return [j for j in self.jogos if j.ponte_confirmada]

    def por_api(self) -> dict[str, list[Prontuario]]:
        saida: dict[str, list[Prontuario]] = {v.value: [] for v in Veredito}
        for jogo in self.jogos:
            saida[jogo.api.value].append(jogo)
        return saida

    def frase(self) -> str:
        """Uma linha para a tela. Nomeia, nunca só conta."""
        if not self.jogos:
            return "Nenhum jogo da Steam instalado por aqui."
        confirmadas = len(self.com_ponte_confirmada)
        pontes = (
            f" {confirmadas} com ponte já confirmada." if confirmadas else ""
        )
        impedidos = self.impedidos
        if not impedidos:
            return (
                f"{len(self.jogos)} jogos, nenhum com pendência conhecida "
                f"({len(self.dependem_de_espelho)} dependem do espelho "
                f"XInput).{pontes}"
            )
        nomes = ", ".join(j.nome for j in impedidos[:3])
        resto = f" e mais {len(impedidos) - 3}" if len(impedidos) > 3 else ""
        automaticos = len(self.curaveis_sozinho)
        cauda = (
            f" O Hefesto repõe {automaticos} ao salvar um perfil."
            if automaticos
            else " Nenhuma se conserta sozinha — veja o detalhe de cada uma."
        )
        return f"Com pendência: {nomes}{resto}.{cauda}{pontes}"

    def como_dicionario(self) -> dict[str, object]:
        return {
            "jogos": [j.como_dicionario() for j in self.jogos],
            "erros": list(self.erros),
            "resumo": {
                "total": len(self.jogos),
                "impedidos": len(self.impedidos),
                "curaveis_sozinho": len(self.curaveis_sozinho),
                "dependem_de_espelho": len(self.dependem_de_espelho),
                "com_ponte_confirmada": len(self.com_ponte_confirmada),
                "por_api": {k: len(v) for k, v in self.por_api().items()},
            },
        }


def e_infraestrutura(nome: str) -> bool:
    """O `.acf` é ferramenta da Steam (Proton, runtime, redistribuíveis)?"""
    return _INFRAESTRUTURA_RE.match(nome.strip()) is not None


def _campos_do_manifesto(texto: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for linha in texto.splitlines():
        par = _PAR_ACF.match(linha)
        if par is not None:
            campos.setdefault(
                _desescapar_acf(par.group("chave")).lower(),
                _desescapar_acf(par.group("valor")),
            )
    return campos


def jogos_instalados(home: Path | None = None) -> list[tuple[str, str, Path | None]]:
    """`[(appid, nome, raiz)]` dos jogos com `appmanifest` em disco."""
    achados: dict[str, tuple[str, str, Path | None]] = {}
    for pasta in pastas_steamapps(home):
        try:
            manifestos = sorted(pasta.glob("appmanifest_*.acf"))
        except OSError:  # pragma: no cover - pasta sumiu entre o listar e o ler
            continue
        for acf in manifestos:
            try:
                campos = _campos_do_manifesto(acf.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            appid = campos.get("appid", "").strip()
            nome = campos.get("name", "").strip()
            if not appid or not nome or e_infraestrutura(nome):
                continue
            instalada = campos.get("installdir", "").strip()
            raiz = pasta / "common" / instalada if instalada else None
            if raiz is not None and not raiz.is_dir():
                raiz = None
            achados.setdefault(appid, (appid, nome, raiz))
    return sorted(achados.values(), key=lambda t: t[1].lower())


def _steam_input_do_vdf(texto: str) -> tuple[dict[str, str], str | None]:
    """`({appid: UseSteamControllerConfig}, SteamController_PSSupport global)`.

    SUBSTITUÍDO em 19/08/2026 (PONTE-STEAM-INPUT-01). A versão anterior aceitava
    o `UseSteamControllerConfig` de QUALQUER bloco chamado `apps` (`pilha[-2] ==
    "apps"`) — o mesmo descuido que o `ARVORE-ERRADA-01` já havia curado do lado
    das `LaunchOptions`, e que aqui devolvia o valor da ÚLTIMA árvore em que o
    appid aparecesse. Quem sabe onde esta chave mora é o `steam_input_ponte`, e
    ele **procura** a árvore viva em vez de a supor: a medição de 19/08 mostrou
    que ela NÃO é a árvore canônica das `LaunchOptions` (as onze ocorrências da
    chave, no arquivo dela, estão em `UserLocalConfigStore/apps`).

    Um arquivo em que as duas réguas discordam, ou em que a árvore viva não se
    prova, devolve dicionário VAZIO: o prontuário passa a dizer "herdado" em vez
    de inventar um valor. Silêncio honesto vale mais que número convincente.
    """
    global_ps: str | None = None
    pilha: list[str] = []
    pendente: str | None = None
    for cru in texto.splitlines():
        linha = cru.strip()
        if not linha:
            continue
        if linha == "{":
            pilha.append(pendente if pendente is not None else "")
            pendente = None
            continue
        if linha == "}":
            if pilha:
                pilha.pop()
            pendente = None
            continue
        par = _PAR_ACF.match(cru)
        if par is not None:
            pendente = None
            if _desescapar_acf(par.group("chave")).lower() == _PS_SUPPORT_GLOBAL:
                global_ps = _desescapar_acf(par.group("valor"))
            continue
        so_chave = _SO_CHAVE_RE.match(cru)
        if so_chave is not None:
            pendente = _desescapar_acf(so_chave.group(1))

    arvores = ler_arvores(texto)
    if conferir_reguas(texto, arvores) is not None:
        return {}, global_ps
    viva = arvore_viva(arvores)
    if viva is None:
        return {}, global_ps
    return {appid: valor for appid, (valor, _) in viva.chaves.items()}, global_ps


def levantar_censo(
    home: Path | None = None,
    *,
    allowlist: Sequence[str] | None = None,
    examinar: bool = True,
    pontes: dict[str, Ponte] | None = None,
) -> Censo:
    """A fotografia read-only de toda a biblioteca instalada."""
    linhas: dict[str, str | None] = {}
    steam_input: dict[str, str] = {}
    global_ps: str | None = None
    erros: list[str] = []
    for vdf in discover_vdfs(home):
        if is_sandboxed_layout(vdf):
            continue
        try:
            texto = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            erros.append(f"{vdf}: {exc}")
            continue
        for appid, valor in read_apps_by_appid(texto).items():
            linhas.setdefault(appid, valor)
        do_vdf, ps = _steam_input_do_vdf(texto)
        for appid, valor in do_vdf.items():
            steam_input.setdefault(appid, valor)
        if global_ps is None:
            global_ps = ps

    if allowlist is None:
        try:
            allowlist = parse_steam_input_allowlist(
                steam_input_allowlist_path().read_text(encoding="utf-8")
            )
        except OSError:
            allowlist = []
    permitidos = {str(a).strip() for a in allowlist}
    carimbos = pontes if pontes is not None else pontes_confirmadas()

    fichas: list[Prontuario] = []
    for appid, nome, raiz in jogos_instalados(home):
        evidencia: Evidencia | None = None
        if raiz is not None and examinar:
            try:
                evidencia = examinar_pasta(raiz)
            except OSError as exc:  # pragma: no cover - permissão no meio da varredura
                erros.append(f"{nome}: {exc}")
        fichas.append(
            Prontuario(
                appid=appid,
                nome=nome,
                raiz=raiz,
                linha=linhas.get(appid),
                evidencia=evidencia,
                steam_input=steam_input.get(appid),
                steam_input_global=global_ps,
                na_allowlist=appid in permitidos,
                ponte=carimbos.get(appid),
            )
        )
    return Censo(jogos=fichas, erros=erros)


CURA_NADA = "nada_a_curar"
CURA_FEITA = "curado"
CURA_ADIADA = "adiado"
CURA_SO_MANUAL = "so_reparo_manual"


@dataclass(frozen=True)
class Cura:
    """O que o produto consertou sozinho, e o que ele NÃO consertou."""

    status: str
    desfechos: dict[str, str] = field(default_factory=dict)
    tocados: dict[str, list[str]] = field(default_factory=dict)
    manuais: list[str] = field(default_factory=list)
    simulacao: bool = False

    def frase(self) -> str:
        if self.status == CURA_NADA:
            return "Nada a consertar sozinho."
        if self.status == CURA_ADIADA:
            return (
                "Tenho conserto para fazer, mas a Steam (ou um jogo) está "
                "aberta — faço assim que ela fechar."
            )
        if self.status == CURA_SO_MANUAL:
            return "O que sobrou só se conserta à mão — está descrito por jogo."
        tudo = sorted({a for lista in self.tocados.values() for a in lista})
        verbo = "Consertaria" if self.simulacao else "Consertei"
        cauda = " (simulação: nada foi escrito)" if self.simulacao else ""
        return f"{verbo} sozinho: {len(tudo)} jogo(s) — {', '.join(tudo)}.{cauda}"


def _curar_excecao_inerte(
    home: Path | None, *, dry_run: bool
) -> tuple[str, list[str]]:
    """A lista de exceções deixa de ser inerte: o produto LIGA o Steam Input."""
    status, _estado, detalhe = garantir_ponte(home, dry_run=dry_run)
    tocados = [
        item["appid"]
        for item in detalhe
        if item["desfecho"] == PONTE_LIGADA and item["appid"]
    ]
    return status, tocados


def _curar_sem_wrapper(home: Path | None, *, dry_run: bool) -> tuple[str, list[str]]:
    """A reposição do `hefesto-launch`, que a sentinela já sabia fazer.

    Ela roda no gesto de salvar/aplicar um perfil e no guarda; entra aqui para
    que a tabela `_CURAS` seja a lista COMPLETA do que o produto conserta
    sozinho, e não uma amostra. Rodar duas vezes no mesmo ciclo é inócuo: o
    reparo delega ao `apply_wrapper_to_all_games`, que pula quem já tem.
    """
    try:
        from .sentinela_do_wrapper import reparar_ou_adiar
    except ImportError:  # pragma: no cover - executado como script avulso
        from sentinela_do_wrapper import reparar_ou_adiar  # type: ignore[no-redef]
    status, _censo, resultado = reparar_ou_adiar(home, dry_run=dry_run)
    tocados = (
        [item["appid"] for item in resultado["applied"]] if resultado else []
    )
    return status, tocados


_CURAS: dict[str, Callable[..., tuple[str, list[str]]]] = {
    EXCECAO_INERTE: _curar_excecao_inerte,
    SEM_WRAPPER: _curar_sem_wrapper,
    LINHA_INTOCAVEL: _curar_sem_wrapper,
}


def curar_o_que_e_automatico(
    home: Path | None = None, *, dry_run: bool = False, censo: Censo | None = None
) -> Cura:
    """Conserta os estorvos que o prontuário declara automáticos. Sem clique."""
    ficha = censo if censo is not None else levantar_censo(home, examinar=False)
    presentes: set[str] = set()
    manuais: set[str] = set()
    for jogo in ficha.impedidos:
        for estorvo in jogo.estorvos:
            if estorvo.automatica:
                presentes.add(estorvo.chave)
            else:
                manuais.add(estorvo.chave)
    if not presentes:
        return Cura(
            status=CURA_SO_MANUAL if manuais else CURA_NADA,
            manuais=sorted(manuais),
        )
    desfechos: dict[str, str] = {}
    tocados: dict[str, list[str]] = {}
    for chave in sorted(presentes):
        cura = _CURAS.get(chave)
        if cura is None:
            manuais.add(chave)
            continue
        status, alvos = cura(home, dry_run=dry_run)
        desfechos[chave] = status
        if alvos:
            tocados[chave] = alvos
    if any(t for t in tocados.values()):
        estado = CURA_FEITA
    elif any(d.startswith("adiado") for d in desfechos.values()):
        estado = CURA_ADIADA
    elif manuais:
        estado = CURA_SO_MANUAL
    elif all(d == PONTE_NADA for d in desfechos.values()):
        estado = CURA_NADA
    else:
        estado = CURA_ADIADA
    return Cura(
        status=estado,
        desfechos=desfechos,
        tocados=tocados,
        manuais=sorted(manuais),
        simulacao=dry_run,
    )


def _texto_da_ponte(ponte: Ponte | None) -> str:
    """A ponte carimbada em uma coluna de terminal, ou o travessão do "não sei"."""
    if ponte is None:
        return "-"
    if ponte.kind == "gamepad":
        base = ponte.gamepad_flavor or "gamepad"
    elif ponte.kind == "desktop":
        base = "mouse_teclado"
    else:
        base = ponte.kind
    return f"{base}+steam_input" if ponte.steam_input else base


def _tabela(censo: Censo) -> str:
    """O relatório de terminal — uma linha por jogo, e o nome sempre."""
    largura = max((len(j.nome) for j in censo.jogos), default=4)
    largura = min(largura, 34)
    linhas = [
        f"{'jogo':{largura}} | {'veredito':26} | {'api':18} | wrapper | "
        f"{'ponte confirmada':20} | Steam Input",
        "-" * (largura + 92),
    ]
    for jogo in censo.jogos:
        si = jogo.steam_input_ligado
        texto_si = "herdado" if si is None else ("ligado" if si else "desligado")
        if jogo.na_allowlist:
            texto_si += " (allowlist)"
        linhas.append(
            f"{jogo.nome[:largura]:{largura}} | {jogo.veredito:26} | "
            f"{jogo.api.value:18} | {'sim' if jogo.tem_wrapper else 'NÃO':7} | "
            f"{_texto_da_ponte(jogo.ponte):20} | {texto_si}"
        )
    for jogo in censo.impedidos:
        linhas.append("")
        linhas.append(f"  {jogo.nome}:")
        for estorvo in jogo.estorvos:
            marca = "o Hefesto repõe sozinho" if estorvo.automatica else "só reparo manual"
            linhas.append(f"    - {estorvo.o_que}")
            linhas.append(f"      cura: {estorvo.a_cura} ({marca})")
    linhas.append("")
    linhas.append(censo.frase())
    return "\n".join(linhas)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="a forma JSON, para `jq`")
    ap.add_argument(
        "--rapido",
        action="store_true",
        help="não varre os executáveis (só a linha de inicialização)",
    )
    ap.add_argument(
        "--curar",
        action="store_true",
        help="conserta o que o prontuário declara automático (sem clique dela)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="não escreve nada (com --curar)"
    )
    args = ap.parse_args(list(argv) if argv is not None else None)
    if args.curar:
        cura = curar_o_que_e_automatico(dry_run=args.dry_run)
        print(f"[prontuario] resultado={cura.status}")
        for chave, desfecho in sorted(cura.desfechos.items()):
            alvos = ", ".join(cura.tocados.get(chave, ())) or "-"
            print(f"[prontuario] {chave}: {desfecho} ({alvos})")
        for chave in cura.manuais:
            print(f"[prontuario] {chave}: só reparo manual")
        print(f"[prontuario] {cura.frase()}")
        return 0
    censo = levantar_censo(examinar=not args.rapido)
    if args.json:
        print(json.dumps(censo.como_dicionario(), ensure_ascii=False, indent=2))
    else:
        print(_tabela(censo))
    return 1 if censo.impedidos else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
