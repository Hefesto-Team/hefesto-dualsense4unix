"""O censo dos lançadores que NÃO são a Steam — LANCADORES-ZERO-01, 09/09/2026."""
from __future__ import annotations

import configparser
import contextlib
import json
import os
import re
import selectors
import shutil
import signal
import sqlite3
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from hefesto_dualsense4unix.integrations.identidade_de_janela import (
    umu_por_chave_do_heroic,
)

NUNCA_ABERTO = "nunca_aberto"
LIDO = "lido"
ILEGIVEL = "ilegivel"

SEM_BIBLIOTECA = "sem_biblioteca"

FRASE_NUNCA_ABERTO = "Abra {nome} uma vez e o Hefesto lê a biblioteca."


@dataclass(frozen=True)
class JogoDoLancador:
    """Um jogo na biblioteca de um lançador que não é a Steam."""

    chave: str
    nome: str
    loja: str = ""
    instalado: bool = False
    caminho: Path | None = None
    executavel: str = ""
    #: `integrations/identidade_de_janela.py` para a medição que a estabeleceu.
    umu_id: str = ""
    appid_da_steam: str = ""
    dlc: bool = False
    configuracao: Path | None = None
    pelo_proton: bool = False
    #: O pedaço do título da janela que é só deste jogo (o ID que o emulador
    #: escreve ali, como ``PPSA21567``), devolvido pelo leitor de uma
    #: modificação. É por ele que o perfil casa quando a janela é a do emulador
    #: para todos os jogos e o resto do título muda a cada segundo.
    titulo_do_jogo: str = ""

    @property
    def classe_de_janela(self) -> str:
        """A `wm_class` que este jogo vai anunciar — ou ``""`` quando não se sabe.

        **O CORPO MUDOU DE CASA EM 21/09/2026, E A DERIVAÇÃO CAIU JUNTO.** Quem
        responde é `integrations/identidade_de_janela.classe_de_janela`, e a
        razão inteira — com a medição que a derrubou — está escrita lá.

        O QUE ESTA PROPRIEDADE DIZIA, e por quê. Ela devolvia o basename do
        `install.executable`: `retail/gotg.exe` virava `gotg.exe`. A nota de
        11/09/2026 que morava aqui declarava que isso **nunca fora medido** —
        *"ninguém abriu Guardiões da Galáxia e leu a classe da janela viva"* —
        e escrevia o degrau que fecharia, com as duas respostas possíveis:

            *"resposta `gotg.exe` → a derivação vira medição e esta nota sai;
            resposta qualquer outra (o Heroic embrulha o jogo num script, e a
            janela pode anunciar o wrapper) → o `executavel` **deixa de ser a
            chave**."*

        **EM 21/09/2026 ELA ABRIU O JOGO E A RESPOSTA FOI A SEGUNDA:**
        ``WM_CLASS = "steam_app_1088850"``. O Heroic lança por `umu`, que monta
        a pilha da Steam e exporta `SteamAppId`; o Proton batiza a janela por
        ele. O `executavel` deixou de ser a chave no mesmo minuto.

        **O ESTRAGO ESTAVA MEDIDO NO PERFIL DO USUÁRIO:**
        ``window_class: ["gotg.exe"]`` é uma regra que nunca casa — nenhum
        perfil ativava, nenhuma feature chegava ao jogo, e a queixa de uso foi a
        leitura certa: *"o Hefesto não é identificado e não funciona lá"*.

        O QUE CONTINUA VALENDO da nota antiga: os três emuladores (RetroArch,
        Dolphin, mGBA) são **UM processo para todas as ROMs**, então a janela é
        a do emulador e não a do jogo. Eles não têm `umu_id` nem appid, caem no
        «não sei», e quem chama não oferece a linha — que é a mesma conclusão,
        agora pelo caminho certo.
        """
        from hefesto_dualsense4unix.integrations.identidade_de_janela import (
            classe_de_janela,
        )

        return classe_de_janela(
            umu_id=self.umu_id, appid_da_steam=self.appid_da_steam,
            executavel=self.executavel)

    @property
    def e_acessorio(self) -> bool:
        """Isto é conteúdo adicional, e não um jogo?"""
        return self.dlc


@dataclass(frozen=True)
class BibliotecaDoLancador:
    """O que se sabe da biblioteca de UM lançador."""

    lancador: str
    estado: str = NUNCA_ABERTO
    onde: Path | None = None
    jogos: list[JogoDoLancador] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

    @property
    def instalados(self) -> list[JogoDoLancador]:
        return [j for j in self.jogos if j.instalado]

    @property
    def resumo(self) -> str:
        """A linha que o cartão imprime debaixo do selo."""
        if self.estado == SEM_BIBLIOTECA:
            return ""
        if self.estado == NUNCA_ABERTO:
            return FRASE_NUNCA_ABERTO.format(nome=self.lancador)
        if self.estado == ILEGIVEL:
            return f"A biblioteca está aqui e não pôde ser lida: {self.erros[0]}" \
                if self.erros else "A biblioteca está aqui e não pôde ser lida."
        n, k = len(self.jogos), len(self.instalados)
        if not n:
            return "A biblioteca está vazia."
        return (f"{n} {'jogo' if n == 1 else 'jogos'} na biblioteca · "
                f"{k} {'instalado' if k == 1 else 'instalados'}")


# `_ONDE` (o app id do Flatpak e a pasta de cada programa), `_CONFIG_CAI_NOS_DADOS`, `_LEITORES`
# e `_DO_CARTAO` NÃO são listas daqui: vêm dos manifestos dos lançadores de fábrica, lidos no fim
# do arquivo (OS-SEIS-LANCADORES-VIRAM-MODIFICACOES-OFICIAIS-01).


@dataclass(frozen=True)
class _Onde:
    """Onde o censo procura: o lar, as duas pastas do XDG dele e a raiz do Flatpak."""

    lar: Path
    config: Path
    dados: Path
    raiz_sistema: Path | None = None


def _do_ambiente(variavel: str) -> Path | None:
    """A pasta desta variável do XDG, quando o ambiente a dá absoluta."""
    valor = os.environ.get(variavel, "").strip()
    return Path(valor) if os.path.isabs(valor) else None


def _onde(lar: Path | None = None, xdg_config: Path | None = None,
          xdg_data: Path | None = None, raiz_sistema: Path | None = None) -> _Onde:
    """O :class:`_Onde` de quem chama: o lar de verdade com o XDG do ambiente,"""
    if lar is None:
        lar = Path.home()
        xdg_config = xdg_config or _do_ambiente("XDG_CONFIG_HOME")
        xdg_data = xdg_data or _do_ambiente("XDG_DATA_HOME")
    return _Onde(lar, xdg_config or lar / ".config", xdg_data or lar / ".local/share",
                 raiz_sistema)


def _casas(lancador: str, onde: _Onde) -> tuple[tuple[Path, Path], ...]:
    """``((config, dados), ...)`` deste lançador: o Flatpak primeiro, o nativo depois."""
    app_id, sub = _ONDE.get(lancador, ("", ""))
    if not sub:
        return ()
    caixa = onde.lar / ".var/app" / app_id
    return ((caixa / "config" / sub, caixa / "data" / sub),
            (onde.config / sub, onde.dados / sub))


def _pasta_da_casa(lancador: str, config: Path, dados: Path) -> Path | None:
    """A pasta de configuração numa casa, pela regra do lançador; ``None`` = não há."""
    if config.is_dir():
        return config
    if lancador in _CONFIG_CAI_NOS_DADOS and dados.is_dir():
        return dados
    return None


def _pastas_lidas(lancador: str, onde: _Onde) -> tuple[Path, ...]:
    """As pastas de configuração que o censo lê, pela regra das duas casas."""
    achadas = [(i, pasta) for i, (config, dados) in enumerate(_casas(lancador, onde))
               if (pasta := _pasta_da_casa(lancador, config, dados)) is not None]
    if len(achadas) < 2:
        return tuple(pasta for _, pasta in achadas)
    instalados = _instalacoes(lancador, onde)
    escolhidas = tuple(pasta for i, pasta in achadas if instalados[i])
    return escolhidas or (achadas[0][1],)


def _instalacoes(lancador: str, onde: _Onde) -> tuple[bool, bool]:
    """``(o Flatpak está instalado, o nativo está instalado)`` — e nunca levanta."""
    app_id, _sub = _ONDE[lancador]
    try:
        from hefesto_dualsense4unix.integrations import sandbox_dos_lancadores as caixa

        no_flatpak = bool(caixa.app_ids_instalados((app_id,), onde.lar, onde.raiz_sistema))
    except Exception:
        no_flatpak = False
    try:
        nativo = _instalado_no_nativo(lancador, onde)
    except Exception:
        nativo = False
    return no_flatpak, nativo


def _agulhas_do_nativo(lancador: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``(atalhos, comandos)`` do programa nativo deste lançador."""
    cartao = next((c for c, nomes in _DO_CARTAO.items() if lancador in nomes), "")
    item = next((f.bloco for f in DE_FABRICA if f.bloco.chave == cartao and not f.interior_lido),
                None)
    if item is None:
        return (), ()
    if len(_DO_CARTAO[cartao]) == 1:
        return item.atalhos, item.comandos
    app_id, sub = _ONDE[lancador]

    def dele(nome: str) -> bool:
        return nome == app_id or nome.casefold().startswith(sub.casefold())

    return (tuple(a for a in item.atalhos if dele(a)),
            tuple(c for c in item.comandos if dele(c)))


def _e_dos_exports_do_flatpak(pasta: Path) -> bool:
    """A pasta de `.desktop` que o Flatpak exporta (`…/flatpak/exports/share/applications`)."""
    partes = pasta.parts
    return any(partes[i:i + 2] == ("flatpak", "exports") for i in range(len(partes) - 1))


def _instalado_no_nativo(lancador: str, onde: _Onde) -> bool:
    """O programa nativo deste lançador está instalado nesta máquina?

    Como o procurador da aba Lançadores acha o programa: o `.desktop` numa pasta
    de atalhos (`jogos_locais.pastas_de_atalhos`, mais a `applications` do XDG
    deste lar), ou o comando no `PATH`. **A pasta de exports do Flatpak não
    conta:** o `net.lutris.Lutris.desktop` tem o mesmo nome nas duas
    instalações, e é a pasta que diz qual. **E o `PATH` sozinho não basta:** o
    censo também roda no serviço, com o `PATH` do systemd de usuário, e a
    distribuição põe o `lutris` e a `steam` em `/usr/games`; o `.desktop` é o
    que acha o nativo ali.
    """
    import shutil

    atalhos, comandos = _agulhas_do_nativo(lancador)
    try:
        from hefesto_dualsense4unix.integrations import jogos_locais as jl

        do_motor = list(jl.pastas_de_atalhos())
    except Exception:
        do_motor = []
    pastas = list(dict.fromkeys([onde.dados / "applications", *do_motor]))
    for pasta in pastas:
        if _e_dos_exports_do_flatpak(pasta):
            continue
        for stem in atalhos:
            with contextlib.suppress(OSError):
                if (pasta / f"{stem}.desktop").is_file():
                    return True
    return any(shutil.which(comando) for comando in comandos)


def _pasta_de_config(lancador: str, lar: Path | None = None) -> Path | None:
    """A primeira pasta que o censo lê deste lançador (:func:`_pastas_lidas`);"""
    pastas = _pastas_lidas(lancador, _onde(lar))
    return pastas[0] if pastas else None


def pastas_lidas(lancador: str, lar: Path | None = None, *,
                 xdg_config: Path | None = None, xdg_data: Path | None = None,
                 raiz_sistema: Path | None = None) -> tuple[Path, ...]:
    """As pastas de configuração que o censo lê deste lançador — a regra das"""
    return _pastas_lidas(lancador, _onde(lar, xdg_config, xdg_data, raiz_sistema))


def pastas_que_existem(lancador: str, lar: Path | None = None, *,
                       xdg_config: Path | None = None,
                       xdg_data: Path | None = None) -> tuple[Path, ...]:
    """Toda pasta de configuração deste lançador que existe, instalado ou não."""
    return tuple(pasta for config, dados in _casas(lancador, _onde(lar, xdg_config, xdg_data))
                 if (pasta := _pasta_da_casa(lancador, config, dados)) is not None)


def pasta_do_flatpak(lancador: str, lar: Path | None = None) -> Path | None:
    """A pasta de configuração da casa FLATPAK deste lançador, pela mesma regra."""
    casas = _casas(lancador, _onde(lar))
    return _pasta_da_casa(lancador, *casas[0]) if casas else None


def _json(caminho: Path) -> object | None:
    """O JSON deste arquivo, ou `None` — e NUNCA levanta."""
    try:
        return cast("object", json.loads(caminho.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


_REGISTROS_DO_HEROIC: dict[str, tuple[str, ...]] = {
    "legendary": ("legendaryConfig/legendary/installed.json",
                  "legendaryConfig/legendary/third-party-installed.json"),
    "gog": ("gog_store/installed.json",),
    "nile": ("nile_config/nile/installed.json",),
}


def _itens_do_registro(arq: str, rel: str, dado: object) -> dict[str, dict[str, object]] | None:
    """``{chave: o que o registro diz do jogo}`` na forma que o Heroic grava;"""
    fora: dict[str, dict[str, object]] = {}
    if rel.endswith("third-party-installed.json"):
        if not isinstance(dado, list):
            return None
        for par in dado:
            if isinstance(par, list) and par and isinstance(par[0], str) and par[0]:
                fora[par[0]] = {"app_name": par[0]}
        return fora
    if arq == "legendary":
        if not isinstance(dado, dict):
            return None
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in dado.items()}
    if arq == "gog":
        lista = dado.get("installed", []) if isinstance(dado, dict) else None
        campo = "appName"
    else:
        lista, campo = dado, "id"
    if not isinstance(lista, list):
        return None
    for item in lista:
        chave = item.get(campo) if isinstance(item, dict) else None
        if isinstance(chave, str) and chave:
            fora[chave] = item
    return fora


def _registro_do_heroic(pasta: Path, arq: str
                        ) -> tuple[dict[str, dict[str, object]], bool, list[str]]:
    """``(os instalados desta loja, o registro dela existe, erros)``."""
    instalados: dict[str, dict[str, object]] = {}
    erros: list[str] = []
    principal, *outros = _REGISTROS_DO_HEROIC[arq]
    existe = os.path.lexists(pasta / principal)
    for rel in (principal, *outros):
        alvo = pasta / rel
        if not os.path.lexists(alvo):
            continue
        itens = _itens_do_registro(arq, rel, _json(alvo))
        if itens is None:
            erros.append(f"{rel} não se lê na forma que o Heroic grava")
            continue
        for chave, dado in itens.items():
            instalados.setdefault(chave, dado)
    return instalados, existe, erros


def _heroic(pasta: Path) -> BibliotecaDoLancador:
    """As TRÊS lojas do Heroic — Epic (legendary), GOG e Amazon (nile)."""
    cache = pasta / "store_cache"
    jogos: list[JogoDoLancador] = []
    erros: list[str] = []
    umu = umu_por_chave_do_heroic(cache)
    lojas = (("legendary", "Epic", "library", "app_name", "title"),
             ("gog", "GOG", "games", "app_name", "title"),
             ("nile", "Amazon", "library", "id", "product_title"))
    for arq, loja, campo, ch_id, ch_nome in lojas:
        dado = _json(cache / f"{arq}_library.json")
        if dado is None:
            continue
        if isinstance(dado, dict) and campo not in dado:
            continue
        itens = dado.get(campo) if isinstance(dado, dict) else None
        if not isinstance(itens, list):
            erros.append(f"{arq}_library.json não traz `{campo}` como lista")
            continue
        itens = [it for it in itens if isinstance(it, dict)]
        registro, existe, erros_da_loja = _registro_do_heroic(pasta, arq)
        if not existe and any(
                it.get("is_installed") and not _e_dlc_na_biblioteca(it)
                and _chave_do_heroic(it, ch_id) not in registro
                for it in itens):
            erros_da_loja.append(f"{_REGISTROS_DO_HEROIC[arq][0]} não existe, e a "
                                 f"biblioteca diz que há jogo instalado")
        erros.extend(erros_da_loja)
        for it in itens:
            chave = _chave_do_heroic(it, ch_id)
            if not chave:
                continue
            instalacao = it.get("install")
            instalacao = instalacao if isinstance(instalacao, dict) else {}
            do_registro = registro.get(chave)
            dele = do_registro if isinstance(do_registro, dict) else {}
            caminho = (instalacao.get("install_path") or dele.get("install_path")
                       or dele.get("path"))
            jogo = JogoDoLancador(
                chave=chave,
                nome=str(it.get(ch_nome) or it.get("title") or chave),
                loja=loja,
                instalado=do_registro is not None or (
                    bool(erros_da_loja) and bool(it.get("is_installed"))),
                caminho=Path(str(caminho)) if caminho else None,
                executavel=str(instalacao.get("executable") or dele.get("executable") or ""),
                umu_id=umu.get(chave, ""),
                dlc=bool(instalacao.get("is_dlc") or dele.get("is_dlc")))
            if jogo.e_acessorio:
                continue
            jogos.append(jogo)
    return BibliotecaDoLancador("Heroic", LIDO, pasta, jogos, erros)


def _chave_do_heroic(item: dict[str, object], ch_id: str) -> str:
    """A chave de um item da biblioteca do Heroic (`app_name`, ou o `id` da Amazon)."""
    return str(item.get(ch_id) or item.get("app_name") or item.get("id") or "")


def _e_dlc_na_biblioteca(item: dict[str, object]) -> bool:
    """O item da biblioteca se declara acessório (`install.is_dlc`)."""
    instalacao = item.get("install")
    return isinstance(instalacao, dict) and bool(instalacao.get("is_dlc"))


_COLUNAS_DO_LUTRIS = ("name", "slug", "executable", "directory", "installed",
                      "runner", "service", "service_id", "configpath")

_COLUNAS_EXIGIDAS_DO_LUTRIS = ("name", "slug")

_RUNNER_DO_UMU = "wine"

_VERSAO_PADRAO_DO_LUTRIS = "ge-proton"

_SERVICO_DA_STEAM = "steam"


def _lutris(pasta: Path, lar: Path | None = None, *,
            onde: _Onde | None = None) -> BibliotecaDoLancador:
    """A biblioteca do Lutris — do `pga.db`, que é onde ela mora.

    **O LEITOR ANTIGO OLHAVA O ARQUIVO ERRADO, e o sintoma era a AUSÊNCIA de
    dado.** Ele lia `games/*.yml` e devolvia o `stem` como nome. Medido no
    disco do usuário em 11/09/2026:

        ~/.var/app/net.lutris.Lutris/config/lutris  ->  data/lutris (symlink)
        data/lutris/games/   0 arquivos
        data/lutris/pga.db   tabela `games`, 23 colunas

    O `games/*.yml` só nasce para jogo com configuração PRÓPRIA; a biblioteca
    é a tabela. Com a pasta vazia o cartão dizia `LIDO · 0 jogos` — que se lê
    como *"o Lutris está vazio"* e não como *"eu olhei no lugar errado"*.

    **E O `.yml` NÃO DAVA A ETIQUETA.** Um `stem` (`sea-of-stars`) não é a
    `wm_class` que a janela anuncia, e é a etiqueta que esta sprint precisa —
    a mesma coisa que o `steam_app_<id>` é para a Steam. O `pga.db` traz
    `executable`, e o basename dele é a classe (ver
    `JogoDoLancador.classe_de_janela`), do mesmo jeito que o
    `install.executable` do Heroic.

    **`sqlite3` É BIBLIOTECA PADRÃO** — nenhuma dependência nova, ao contrário
    do `pyyaml` que o leitor antigo recusou (e recusou com razão: uma
    dependência para ler um nome de arquivo era o custo errado).

    ABERTO EM MODO SOMENTE-LEITURA (`mode=ro`), e é requisito e não zelo: o
    Lutris dela pode estar aberto com o banco na mão, e este módulo é chamado
    da PINTURA de uma aba. `immutable=` seria mais rápido e mentiria sobre um
    arquivo que muda.

    O `.yml` continua entrando, e só ACRESCENTA o que a tabela não tiver: um
    jogo configurado à mão que nunca entrou no banco continua aparecendo, e a
    leitura nova não pode ENCOLHER o que já funcionava.

    **O QUE NÃO FOI MEDIDO, E FICA DECLARADO — 21/09/2026.** O `pga.db` dela
    tem ZERO jogos: o Lutris está instalado e vazio. Então a janela de um jogo
    do Lutris **não foi lida em aparelho nenhum** desta casa, e esta sprint
    aprendeu em 21/09 o preço de derivar no lugar de medir.

    Por isso o que entra aqui é só o degrau que JÁ ESTÁ MEDIDO em outro leitor:
    `service == "steam"` ⇒ `service_id` é o appid da Steam, e um appid da Steam
    vira `steam_app_<N>` — o mesmo fato que a biblioteca da Steam usa há meses.
    Nenhum degrau novo se inventava aqui: jogo do Lutris sem serviço da Steam
    respondia «não sei» e mandava ao «Detectar».

    **02/10/2026 — O DEGRAU 1 ENTROU, LIDO NO FONTE DO LUTRIS
    (A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01).** O jogo da GOG, da Epic, da Humble
    ou da Amazon no Lutris abre pelo umu com o `GAMEID` que o próprio Lutris
    acha (`util/wine/proton.get_game_id`, lido no 0.5.22 instalado nela): o
    `UMU_ID` do ambiente do jogo, ou a loja e o id do jogo no `umu-games.json`
    da casa dele. O umu põe a janela em `steam_app_<N>` — medido no Guardiões
    pelo Heroic em 21/09 (`identidade_de_janela`), que é o mesmo umu. A regra
    está em :class:`_UmuDoLutris`, com as condições do Lutris (o runner `wine`
    e uma versão que seja Proton). A janela de um jogo do Lutris continua sem
    leitura em aparelho nenhum desta casa (o Lutris dela segue vazio).

    :param lar: o lar de quem chama (o padrão é o de verdade, com o XDG do
        ambiente): é nele que se procura o Proton e a pasta de dados do nativo.
        O lar não se deduz do caminho da pasta (02/10/2026): com o XDG
        desviado para `/dados`, a dedução dava `/`.
    """
    onde = _onde(lar) if onde is None else onde
    jogos: list[JogoDoLancador] = []
    erros: list[str] = []
    vistos: set[str] = set()
    ymls_vistos: set[str] = set()
    umu = _UmuDoLutris(pasta, onde)
    banco = Path(umu._conf.get("pga_path") or umu._dados / "pga.db")
    if banco.is_file():
        try:
            conexao = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        except sqlite3.Error as erro:  # pragma: no cover - banco ilegível
            erros.append(f"pga.db não abriu: {erro}")
        else:
            with contextlib.closing(conexao):
                try:
                    tem = {str(c[1]) for c in conexao.execute("PRAGMA table_info(games)")}
                    faltam = [c for c in _COLUNAS_EXIGIDAS_DO_LUTRIS if c not in tem]
                    if faltam:
                        raise sqlite3.OperationalError(
                            "sem a coluna " + ", ".join(faltam) if tem else "sem a tabela")
                    colunas = ", ".join(c if c in tem else f"NULL AS {c}"
                                        for c in _COLUNAS_DO_LUTRIS)
                    linhas = list(
                        conexao.execute(f"SELECT {colunas} FROM games"))
                except sqlite3.Error as erro:
                    erros.append(f"pga.db não traz `games`: {erro}")
                    linhas = []
                for linha in linhas:
                    (nome, slug, executavel, pasta_do_jogo, instalado, runner,
                     servico, id_do_servico, configpath) = linha
                    chave = str(slug or nome or "")
                    if not chave or chave in vistos:
                        continue
                    vistos.add(chave)
                    # O DEGRAU 2 SAI DAQUI. `identidade_de_janela` é quem o
                    numero = str(id_do_servico or "").strip()
                    da_steam = (
                        numero
                        if str(servico or "").strip().casefold()
                        == _SERVICO_DA_STEAM and numero.isdigit()
                        else ""
                    )
                    yml = (pasta / "games" / f"{configpath}.yml"
                           if str(configpath or "").strip() else None)
                    if yml is not None:
                        ymls_vistos.add(yml.name)
                    jogos.append(JogoDoLancador(
                        chave=chave,
                        nome=str(nome or chave),
                        loja="Lutris",
                        instalado=bool(instalado),
                        caminho=(Path(str(pasta_do_jogo))
                                 if pasta_do_jogo else None),
                        executavel=str(executavel or ""),
                        umu_id=(umu.do_jogo(str(runner or ""), str(servico or ""),
                                            str(id_do_servico or ""), yml)
                                if instalado else ""),
                        appid_da_steam=da_steam,
                        configuracao=yml,
                        pelo_proton=bool(instalado) and umu.pelo_proton(
                            str(runner or ""), yml)))
    games = pasta / "games"
    if games.is_dir():
        for p in sorted(games.glob("*.yml")):
            if p.stem in vistos or p.name in ymls_vistos:
                continue
            vistos.add(p.stem)
            jogos.append(JogoDoLancador(
                chave=p.stem, nome=p.stem.replace("-", " "),
                loja="Lutris", instalado=True, caminho=p, configuracao=p))
    jogos.sort(key=lambda j: (j.nome.casefold(), j.chave))
    return BibliotecaDoLancador("Lutris", LIDO, pasta, jogos, erros)


def _ler_yml(alvo: Path) -> dict[str, object] | None:
    """Um `.yml` do Lutris como dicionário; ausente, torto ou sem PyYAML = ``None``."""
    try:
        import yaml
    except ImportError:  # pragma: no cover - o produto declara o PyYAML
        return None
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        dado = yaml.safe_load(texto)
    except yaml.YAMLError:
        return None
    return dado if isinstance(dado, dict) else None


def _secao(dado: dict[str, object] | None, *caminho: str) -> object:
    """``dado[a][b]…`` — ``None`` no primeiro degrau que não é dicionário."""
    atual: object = dado
    for passo in caminho:
        if not isinstance(atual, dict):
            return None
        atual = atual.get(passo)
    return atual


class _UmuDoLutris:
    """O `GAMEID` que o Lutris daria a cada jogo — a regra dele, lida no fonte."""

    def __init__(self, pasta: Path, onde: _Onde) -> None:
        self.pasta = pasta
        self._lar = onde.lar
        self._dados = _pasta_de_dados_do_lutris(pasta, onde)
        self._conf = _conf_do_lutris(pasta)
        self._tabela: dict[tuple[str, str], str] | None = None
        self._versao_do_runner: str | None = None
        self._leu_o_runner = False
        self._ymls: dict[Path, dict[str, object] | None] = {}

    def _yml(self, yml: Path | None) -> dict[str, object] | None:
        """O `.yml` do jogo, lido uma vez por biblioteca."""
        if yml is None:
            return None
        if yml not in self._ymls:
            self._ymls[yml] = _ler_yml(yml)
        return self._ymls[yml]

    def _umu_games(self) -> dict[tuple[str, str], str]:
        if self._tabela is not None:
            return self._tabela
        runtime = Path(self._conf.get("runtime_dir") or self._dados / "runtime")
        dado = _json(runtime / "umu-games" / "umu-games.json")
        tabela: dict[tuple[str, str], str] = {}
        for linha in dado if isinstance(dado, list) else ():
            if not isinstance(linha, dict):
                continue
            loja, appid, umu_id = linha.get("store"), linha.get("appid"), linha.get("umu_id")
            if not loja or not isinstance(umu_id, str) or appid is None:
                continue
            tabela.setdefault((str(loja), str(appid)), umu_id)
        self._tabela = tabela
        return tabela

    def _do_runner(self) -> str | None:
        if not self._leu_o_runner:
            self._leu_o_runner = True
            versao = _secao(_ler_yml(self.pasta / "runners" / "wine.yml"), "wine", "version")
            self._versao_do_runner = str(versao) if versao else None
        return self._versao_do_runner

    def _e_proton(self, versao: str) -> bool:
        """`proton.is_proton_version`: uma pasta com o script `proton` dentro."""
        runners = Path(self._conf.get("runner_dir") or self._dados / "runners")
        lar = self._lar
        locais = [runners / "wine"]
        for steam in (".steam/steam", ".local/share/Steam",
                      ".var/app/com.valvesoftware.Steam/.local/share/Steam"):
            locais += [lar / steam / "compatibilitytools.d", lar / steam / "steamapps/common"]
        return any((onde / versao / "proton").is_file() for onde in locais)

    def pelo_proton(self, runner: str, yml: Path | None) -> bool:
        """O jogo abre pelo umu, e com ele pelo script do Proton?"""
        if runner.strip() != _RUNNER_DO_UMU:
            return False
        versao: str | None = None
        for nivel in (_secao(self._yml(yml), "wine", "version"), self._do_runner()):
            if nivel and str(nivel) != _VERSAO_PADRAO_DO_LUTRIS:
                versao = str(nivel)
                break
        return versao is None or self._e_proton(versao)

    def do_jogo(self, runner: str, servico: str, appid: str, yml: Path | None) -> str:
        """O `umu-<N>` deste jogo, ou ``""``."""
        if not self.pelo_proton(runner, yml):
            return ""
        dado = self._yml(yml)
        proprio = _secao(dado, "system", "env", "UMU_ID")
        if isinstance(proprio, str) and proprio.strip():
            return proprio.strip()
        loja = servico.strip()
        if not loja:
            return ""
        tabela = self._umu_games()
        achado = tabela.get((loja, appid.strip()))
        if achado is None and loja == "humblebundle":
            achado = tabela.get(("humble", appid.strip()))
        return achado or ""


def _pasta_de_dados_do_lutris(pasta: Path, onde: _Onde) -> Path:
    """A pasta de dados do Lutris (o `pga.db`, o `runtime/`), pela regra dele."""
    dados = next((d for c, d in _casas("Lutris", onde) if pasta in (c, d)), pasta)
    for tentativa in (dados, pasta):
        if (tentativa / "pga.db").is_file() or (tentativa / "runtime").is_dir():
            return tentativa
    return pasta


def _conf_do_lutris(pasta: Path) -> dict[str, str]:
    """A seção `[lutris]` do `lutris.conf` — onde o `runtime_dir` pode mudar de lugar."""
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        cfg.read_string((pasta / "lutris.conf").read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error):
        return {}
    return dict(cfg.items("lutris")) if cfg.has_section("lutris") else {}


@dataclass(frozen=True)
class ProtonEmUso:
    """Que versões de Proton os lançadores de fora da Steam usam, e o que não se conseguiu ler.

    O campo das versões traz os nomes como o lançador os grava (a pasta de
    ``compatibilitytools.d`` ou o nome da ferramenta). ``duvida`` lista o que existe e não se lê:
    com ela, quem decide apagar uma versão NÃO apaga (a pasta a mais custa disco; a que saiu a
    menos custa um jogo).
    """

    versoes: frozenset[str] = frozenset()
    duvida: tuple[str, ...] = ()


def _yml_do_lutris(alvo: Path, duvida: list[str]) -> dict[str, object]:
    """Um ``.yml`` do Lutris que EXISTE; torto, ilegível ou sem PyYAML conta como dúvida."""
    try:
        import yaml

        dado = yaml.safe_load(alvo.read_text(encoding="utf-8"))
    except Exception:
        duvida.append(str(alvo))
        return {}
    if dado is None:
        return {}
    if not isinstance(dado, dict):
        duvida.append(str(alvo))
        return {}
    return dado


def _versao_do_wine(dado: dict[str, object]) -> list[str]:
    """``wine.version`` de um ``.yml`` do Lutris, quando há."""
    versao = _secao(dado, "wine", "version")
    return [versao.strip()] if isinstance(versao, str) and versao.strip() else []


def _proton_do_lutris(pasta: Path) -> tuple[list[str], list[str]]:
    """``(versões, dúvidas)`` do Lutris desta pasta: ``runners/wine.yml`` e cada ``games/*.yml``."""
    versoes: list[str] = []
    duvida: list[str] = []
    padrao = pasta / "runners" / "wine.yml"
    if padrao.is_file():
        versoes += _versao_do_wine(_yml_do_lutris(padrao, duvida))
    games = pasta / "games"
    if not os.path.lexists(games):
        return versoes, duvida
    try:
        ymls = sorted(games.glob("*.yml"))
    except OSError:
        return versoes, [*duvida, str(games)]
    for yml in ymls:
        versoes += _versao_do_wine(_yml_do_lutris(yml, duvida))
    return versoes, duvida


def _json_do_heroic(alvo: Path, duvida: list[str]) -> object:
    """O JSON de um arquivo do Heroic que EXISTE; ilegível conta como dúvida."""
    try:
        return cast("object", json.loads(alvo.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        duvida.append(str(alvo))
        return None


def _versoes_da_ferramenta(ferramenta: object) -> list[str]:
    """Do ``wineVersion`` do Heroic (``{bin, name, type}``): o nome e a pasta do ``bin``."""
    if not isinstance(ferramenta, dict):
        return []
    achadas: list[str] = []
    nome = ferramenta.get("name")
    if isinstance(nome, str) and nome.strip():
        achadas.append(nome.strip())
    binario = ferramenta.get("bin")
    if isinstance(binario, str) and binario.strip():
        pasta = Path(binario.strip()).parent.name
        if pasta:
            achadas.append(pasta)
    return achadas


def _proton_do_heroic(pasta: Path) -> tuple[list[str], list[str]]:
    """``(versões, dúvidas)`` do Heroic desta pasta, no formato que ele grava (medido em 16/10).

    ``config.json`` traz o padrão em ``defaultSettings.wineVersion``; cada
    ``GamesConfig/<jogo>.json``
    traz o de um jogo em ``{<jogo>: {wineVersion: {bin, name, type}}}``.
    """
    versoes: list[str] = []
    duvida: list[str] = []
    conf = pasta / "config.json"
    if conf.is_file():
        bruto = _json_do_heroic(conf, duvida)
        if bruto is not None and not isinstance(bruto, dict):
            duvida.append(str(conf))
        padroes = bruto.get("defaultSettings") if isinstance(bruto, dict) else None
        versoes += _versoes_da_ferramenta(
            padroes.get("wineVersion") if isinstance(padroes, dict) else None)
    jogos = pasta / "GamesConfig"
    if not os.path.lexists(jogos):
        return versoes, duvida
    try:
        arquivos = sorted(jogos.glob("*.json"))
    except OSError:
        return versoes, [*duvida, str(jogos)]
    for arquivo in arquivos:
        dado = _json_do_heroic(arquivo, duvida)
        if not isinstance(dado, dict):
            if dado is not None:
                duvida.append(str(arquivo))
            continue
        versoes += _versoes_da_ferramenta(dado.get("wineVersion"))
        for valor in dado.values():
            if isinstance(valor, dict):
                versoes += _versoes_da_ferramenta(valor.get("wineVersion"))
    return versoes, duvida


def proton_em_uso(lar: Path | None = None, *, xdg_config: Path | None = None,
                  xdg_data: Path | None = None) -> ProtonEmUso:
    """Que versões de Proton o Lutris e o Heroic usam, em toda instalação (nativa e Flatpak).

    O dono do saber de onde cada lançador guarda isso. Olha toda pasta de configuração que EXISTE,
    instalado ou não: um lançador que sobrou no disco ainda aponta para o Proton. Nunca levanta; o
    que existe e não se lê entra em ``duvida``.
    """
    versoes: set[str] = set()
    duvida: list[str] = []
    for lancador, leitor in (("Lutris", _proton_do_lutris), ("Heroic", _proton_do_heroic)):
        try:
            pastas = pastas_que_existem(lancador, lar, xdg_config=xdg_config, xdg_data=xdg_data)
        except Exception:
            duvida.append(lancador)
            continue
        for pasta in pastas:
            try:
                achadas, duvidas = leitor(pasta)
            except Exception:
                achadas, duvidas = [], [str(pasta)]
            versoes.update(achadas)
            duvida.extend(duvidas)
    return ProtonEmUso(frozenset(versoes), tuple(duvida))


def _retroarch(pasta: Path) -> BibliotecaDoLancador:
    """As playlists `.lpl` — uma por console, com as ROMs dentro."""
    listas = pasta / "playlists"
    if not listas.is_dir():
        return BibliotecaDoLancador("RetroArch", LIDO, pasta, [], [])
    jogos: list[JogoDoLancador] = []
    erros: list[str] = []
    for lpl in sorted(listas.glob("*.lpl")):
        dado = _json(lpl)
        itens = dado.get("items") if isinstance(dado, dict) else None
        if not isinstance(itens, list):
            erros.append(f"{lpl.name} não traz `items` como lista")
            continue
        for it in itens:
            if not isinstance(it, dict):
                continue
            caminho = str(it.get("path") or "")
            jogos.append(JogoDoLancador(
                chave=caminho, nome=str(it.get("label") or Path(caminho).stem),
                loja=lpl.stem, instalado=bool(caminho),
                caminho=Path(caminho) if caminho else None))
    return BibliotecaDoLancador("RetroArch", LIDO, pasta, jogos, erros)


def _dolphin(pasta: Path) -> BibliotecaDoLancador:
    """As PASTAS de ISO do `Dolphin.ini` (`ISOPath0..N`) — não os jogos."""
    ini = pasta / "Dolphin.ini"
    if not ini.is_file():
        return BibliotecaDoLancador("Dolphin", LIDO, pasta, [], [])
    cfg = configparser.ConfigParser(strict=False)
    try:
        cfg.read_string(ini.read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error) as erro:
        return BibliotecaDoLancador("Dolphin", ILEGIVEL, pasta, [], [str(erro)])
    jogos = [JogoDoLancador(chave=v, nome=Path(v).name or v, loja="Pasta de ISOs",
                            caminho=Path(v))
             for sec in cfg.sections()
             for k, v in cfg.items(sec)
             if k.startswith("isopath") and k[7:].isdigit() and v]
    return BibliotecaDoLancador("Dolphin", LIDO, pasta, jogos, [])


def _mgba(pasta: Path) -> BibliotecaDoLancador:
    """O mGBA guarda os recentes no `config.ini`, seção `[ports.qt]`."""
    ini = pasta / "config.ini"
    if not ini.is_file():
        return BibliotecaDoLancador("mGBA", LIDO, pasta, [], [])
    cfg = configparser.ConfigParser(strict=False)
    try:
        cfg.read_string(ini.read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error) as erro:
        return BibliotecaDoLancador("mGBA", ILEGIVEL, pasta, [], [str(erro)])
    jogos = [JogoDoLancador(chave=v, nome=Path(v).name or v, loja="Recentes",
                            instalado=True, caminho=Path(v))
             for sec in cfg.sections()
             for k, v in cfg.items(sec) if k.startswith("recent.") and v]
    return BibliotecaDoLancador("mGBA", LIDO, pasta, jogos, [])


def _ler(lancador: str, pasta: Path, onde: _Onde) -> BibliotecaDoLancador:
    """O leitor deste lançador sobre UMA pasta — e nunca levanta por disco."""
    try:
        if lancador == "Lutris":
            return _lutris(pasta, onde=onde)
        return _LEITORES[lancador](pasta)
    except OSError as erro:
        return BibliotecaDoLancador(lancador, ILEGIVEL, pasta, [], [str(erro)])


def bibliotecas_por_casa(lancador: str, lar: Path | None = None, *,
                         xdg_config: Path | None = None, xdg_data: Path | None = None,
                         raiz_sistema: Path | None = None) -> list[BibliotecaDoLancador]:
    """A biblioteca de cada pasta que o censo lê (:func:`pastas_lidas`), cada uma"""
    if lancador not in _LEITORES:
        return []
    onde = _onde(lar, xdg_config, xdg_data, raiz_sistema)
    return [_ler(lancador, pasta, onde) for pasta in _pastas_lidas(lancador, onde)]


def _uma_vez_por_jogo(jogos: list[JogoDoLancador]) -> list[JogoDoLancador]:
    """Cada jogo do Heroic uma vez, pela loja e pela chave, o instalado na frente."""
    fora: dict[tuple[str, str], JogoDoLancador] = {}
    for jogo in jogos:
        ja = fora.get((jogo.loja, jogo.chave))
        if ja is None or (jogo.instalado and not ja.instalado):
            fora[(jogo.loja, jogo.chave)] = jogo
    return list(fora.values())


def biblioteca_de(lancador: str, lar: Path | None = None, *,
                  xdg_config: Path | None = None, xdg_data: Path | None = None,
                  raiz_sistema: Path | None = None) -> BibliotecaDoLancador:
    """O que este lançador tem na biblioteca — ou por que não se sabe."""
    if lancador not in _LEITORES:
        return BibliotecaDoLancador(lancador, SEM_BIBLIOTECA, None, [], [])
    partes = bibliotecas_por_casa(lancador, lar, xdg_config=xdg_config,
                                  xdg_data=xdg_data, raiz_sistema=raiz_sistema)
    if not partes:
        return BibliotecaDoLancador(lancador, NUNCA_ABERTO, None, [], [])
    if len(partes) == 1:
        return partes[0]
    lidas = [b for b in partes if b.estado == LIDO]
    jogos = [j for b in lidas for j in b.jogos]
    if lancador == "Heroic":
        jogos = _uma_vez_por_jogo(jogos)
    if lancador == "Lutris":
        jogos.sort(key=lambda j: (j.nome.casefold(), j.chave))
    return BibliotecaDoLancador(
        lancador, LIDO if lidas else partes[0].estado,
        (lidas or partes)[0].onde, jogos, [e for b in partes for e in b.erros])


def biblioteca_do_cartao(chave: str, lar: Path | None = None, *,
                         leitor: LeitorPorProcesso | None = None,
                         ) -> BibliotecaDoLancador:
    """A biblioteca que UM CARTÃO da aba 07 representa.

    O cartão de fábrica é lido pelo leitor de fábrica, sempre; o ``leitor`` de
    uma modificação só responde pelo cartão que não tem um.
    """
    nomes = _DO_CARTAO.get(chave)
    if nomes is None:
        if leitor is not None:
            return ler_por_processo(leitor)
        return BibliotecaDoLancador(chave, SEM_BIBLIOTECA, None, [], [])
    if not nomes:
        return BibliotecaDoLancador(chave, SEM_BIBLIOTECA, None, [], [])
    partes = [biblioteca_de(n, lar) for n in nomes]
    lidas = [b for b in partes if b.estado == LIDO]
    if not lidas:
        return partes[0]
    return BibliotecaDoLancador(
        lancador=" · ".join(nomes),
        estado=LIDO,
        onde=lidas[0].onde,
        jogos=[j for b in lidas for j in b.jogos],
        erros=[e for b in partes for e in b.erros])


# -- o lançador que vem de uma modificação --------------------------------------
#
# O bloco ``lancador`` do ``hefesto-mod.json`` (``mods/manifesto.py`` só confere a
# forma de dicionário; o conteúdo é daqui). Ele é lido sem pydantic, como o resto
# deste módulo, porque o gerador da aba 07 o importa rodando solto.

#: As chaves que o bloco aceita. Outra qualquer recusa o bloco inteiro, como o
#: ``extra="forbid"`` do manifesto: um erro de digitação nunca vira campo calado.
CAMPOS_DO_LANCADOR = frozenset(
    {"rotulo", "atalhos", "comandos", "janelas", "titulo_do_jogo", "leitor"})

#: O prazo do leitor quando o bloco não diz, e o teto do que ele pode pedir. O
#: leitor roda na vigia da aba e no clique da escolha: passar disso é a escolha
#: do jogo esperando a modificação.
PRAZO_DO_LEITOR_S = 5.0
PRAZO_MAXIMO_DO_LEITOR_S = 10.0

#: O teto da saída do leitor e da lista que ela traz. Passou, o leitor é parado
#: e a biblioteca fica «não pôde ser lida»: a memória da janela não é da modificação.
SAIDA_MAXIMA_DO_LEITOR = 1 << 20
JOGOS_MAXIMOS_DO_LEITOR = 5000

_MAXIMO_DE_AGULHAS = 16
_CHAVE_DO_JOGO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class LeitorPorProcesso:
    """O comando que devolve a biblioteca de um lançador de modificação, em JSON.

    A saída é uma lista de objetos com ``chave``, ``nome``, ``caminho`` e
    ``titulo_do_jogo``. O comando é relativo à pasta da modificação (ou um nome
    do ``PATH``, como ``python3``), e roda nela.
    """

    modificacao: str
    rotulo: str
    comando: tuple[str, ...]
    pasta: Path
    prazo_s: float = PRAZO_DO_LEITOR_S
    #: A forma que o ``titulo_do_jogo`` de cada jogo tem de ter (``re.search``).
    #: Vazia, qualquer texto curto serve.
    molde_do_titulo: str = ""


@dataclass(frozen=True)
class LancadorDaModificacao:
    """O bloco ``lancador`` de uma modificação, já conferido."""

    chave: str
    rotulo: str
    atalhos: tuple[str, ...] = ()
    comandos: tuple[str, ...] = ()
    #: As classes de janela (``app_id``) que o emulador anuncia, para o perfil
    #: «todos os jogos» e para a lista de exclusão.
    janelas: tuple[str, ...] = ()
    titulo_do_jogo: str = ""
    leitor: LeitorPorProcesso | None = None


def _agulhas(bloco: dict[str, object], campo: str) -> tuple[str, ...]:
    bruto = bloco.get(campo, [])
    if not isinstance(bruto, list) or not all(isinstance(x, str) for x in bruto):
        raise ValueError(f"«{campo}» precisa ser uma lista de textos")
    limpas = tuple(dict.fromkeys(x.strip() for x in bruto if x.strip()))
    if len(limpas) > _MAXIMO_DE_AGULHAS:
        raise ValueError(f"«{campo}» passa de {_MAXIMO_DE_AGULHAS} itens")
    return limpas


def _leitor_do_bloco(mod_id: str, rotulo: str, bruto: object, pasta: Path,
                     molde: str) -> LeitorPorProcesso:
    if not isinstance(bruto, dict) or set(bruto) - {"executar", "prazo_s"}:
        raise ValueError("«leitor» aceita só «executar» e «prazo_s»")
    executar = bruto.get("executar")
    if (not isinstance(executar, list) or not executar
            or not all(isinstance(x, str) for x in executar) or not executar[0].strip()):
        raise ValueError("«leitor.executar» precisa ser uma lista de textos")
    primeiro = executar[0]
    if primeiro.startswith("/") or ".." in Path(primeiro).parts:
        raise ValueError("«leitor.executar» aponta para fora da pasta da modificação")
    prazo = bruto.get("prazo_s", PRAZO_DO_LEITOR_S)
    if (isinstance(prazo, bool) or not isinstance(prazo, (int, float))
            or not 0 < prazo <= PRAZO_MAXIMO_DO_LEITOR_S):
        raise ValueError(
            f"«leitor.prazo_s» precisa estar entre 0 e {PRAZO_MAXIMO_DO_LEITOR_S:g} s")
    return LeitorPorProcesso(mod_id, rotulo, tuple(executar), pasta, float(prazo), molde)


def lancador_da_modificacao(mod_id: str, bloco: object, pasta: Path
                            ) -> LancadorDaModificacao:
    """Confere o bloco ``lancador`` de uma modificação; recusa com ``ValueError``.

    A chave do cartão é o ``id`` da modificação (o manifesto já o conferiu na
    forma de chave). Uma modificação cujo ``id`` é o de um cartão de fábrica
    (``retroarch``) ensina aquele cartão, como o lançador que a pessoa declara.
    """
    if not isinstance(bloco, dict):
        raise ValueError("«lancador» precisa ser um objeto")
    estranhos = sorted(set(bloco) - CAMPOS_DO_LANCADOR)
    if estranhos:
        raise ValueError(f"«lancador» tem o campo «{estranhos[0]}», que não existe")
    rotulo = bloco.get("rotulo")
    if not isinstance(rotulo, str) or not rotulo.strip() or len(rotulo.strip()) > 60:
        raise ValueError("«lancador.rotulo» precisa ter de 1 a 60 caracteres")
    rotulo = rotulo.strip()
    atalhos, comandos = _agulhas(bloco, "atalhos"), _agulhas(bloco, "comandos")
    if not atalhos and not comandos:
        raise ValueError("«lancador» não diz onde procurar: sem «atalhos» nem «comandos»")
    molde = bloco.get("titulo_do_jogo", "")
    if not isinstance(molde, str) or len(molde) > 200:
        raise ValueError("«lancador.titulo_do_jogo» precisa ser um texto curto")
    if molde:
        try:
            re.compile(molde)
        except re.error as erro:
            raise ValueError(f"«lancador.titulo_do_jogo» não é expressão válida: {erro}") from erro
    leitor = (None if "leitor" not in bloco
              else _leitor_do_bloco(mod_id, rotulo, bloco["leitor"], pasta, molde))
    return LancadorDaModificacao(
        chave=mod_id, rotulo=rotulo, atalhos=atalhos, comandos=comandos,
        janelas=_agulhas(bloco, "janelas"), titulo_do_jogo=molde, leitor=leitor)


def _execucao_escondida() -> tuple[str, ...]:
    """O que a caixa do leitor cobre: o barramento do sistema e a execução da sessão."""
    pastas = ["/run/dbus", os.environ.get("XDG_RUNTIME_DIR", ""), f"/run/user/{os.getuid()}"]
    return tuple(dict.fromkeys(p for p in pastas if p and os.path.isdir(p)))


def linha_do_leitor(leitor: LeitorPorProcesso, comando: list[str],
                    bwrap: str | None) -> list[str]:
    """A linha que abre o leitor: dentro da caixa quando o ``bwrap`` existe.

    A caixa do leitor NÃO é a do processo da modificação
    (``mods/supervisor.comando_na_caixa``), e a diferença é o trabalho dele: a
    do processo esconde a ``HOME``, e o leitor existe para ler a configuração
    do emulador que mora nela (``~/.config/Kyty/Kyty.ini``). Esta deixa a raiz
    inteira visível e SÓ DE LEITURA, sem rede, sem o barramento do sistema,
    sem a execução da sessão (o socket do serviço, o do som, o do Wayland) e
    num espaço de PID próprio, que morre com quem o abriu. Sem ``bwrap``, roda
    sem caixa, como o supervisor faz com o processo.
    """
    if not bwrap:
        return comando
    argv = [bwrap, "--ro-bind", "/", "/", "--unshare-all", "--die-with-parent",
            "--new-session", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    for pasta in _execucao_escondida():
        argv += ["--tmpfs", pasta]
    argv += ["--ro-bind", str(leitor.pasta), str(leitor.pasta),
             "--chdir", str(leitor.pasta), "--", *comando]
    return argv


def _comando_do_leitor(leitor: LeitorPorProcesso) -> list[str] | None:
    primeiro = leitor.pasta / leitor.comando[0]
    if primeiro.is_file():
        return [str(primeiro), *leitor.comando[1:]]
    if "/" not in leitor.comando[0]:
        achado = shutil.which(leitor.comando[0])
        if achado:
            return [achado, *leitor.comando[1:]]
    return None


def _ambiente_do_leitor(leitor: LeitorPorProcesso) -> dict[str, str]:
    ambiente = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "LANG": os.environ.get("LANG", "C.UTF-8"),
                "HOME": os.environ.get("HOME", str(Path.home())),
                "PYTHONDONTWRITEBYTECODE": "1",
                "HEFESTO_MOD_ID": leitor.modificacao}
    for nome in ("XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        if os.environ.get(nome):
            ambiente[nome] = os.environ[nome]
    return ambiente


def _parar(processo: subprocess.Popen[bytes], prazo_s: float) -> None:
    """Para o leitor e o que ele abriu: o grupo é dele (``start_new_session``).

    O ``SIGKILL`` não se recusa, e a espera que recolhe o processo volta logo.
    Ela tem teto só pelo leitor preso no disco (uma pasta de rede morta), e o
    teto é o prazo que a modificação declarou: quem chama nunca espera mais
    que duas vezes o que aceitou esperar.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(processo.pid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        processo.wait(timeout=prazo_s)


def _saida_do_leitor(processo: subprocess.Popen[bytes], prazo_s: float
                     ) -> tuple[bytes | None, str]:
    """``(saída, "")`` ou ``(None, motivo)``. Lê com teto e com prazo, nunca mais."""
    assert processo.stdout is not None
    fim = time.monotonic() + prazo_s
    lido = bytearray()
    with selectors.DefaultSelector() as seletor:
        seletor.register(processo.stdout, selectors.EVENT_READ)
        while True:
            resta = fim - time.monotonic()
            if resta <= 0:
                return None, f"o leitor passou de {prazo_s:g} s"
            if not seletor.select(resta):
                continue
            bloco = os.read(processo.stdout.fileno(), 65536)
            if not bloco:
                break
            lido += bloco
            if len(lido) > SAIDA_MAXIMA_DO_LEITOR:
                return None, "o leitor devolveu mais do que cabe"
    try:
        processo.wait(timeout=max(0.05, fim - time.monotonic()))
    except subprocess.TimeoutExpired:
        return None, f"o leitor passou de {prazo_s:g} s"
    if processo.returncode != 0:
        return None, f"o leitor saiu com o código {processo.returncode}"
    return bytes(lido), ""


def _jogo_do_leitor(linha: object, molde: str) -> JogoDoLancador | None:
    """Uma linha da saída do leitor, conferida; ``None`` quando ela não serve."""
    if not isinstance(linha, dict):
        return None
    chave, nome = linha.get("chave"), linha.get("nome")
    caminho, titulo = linha.get("caminho", ""), linha.get("titulo_do_jogo", "")
    if not isinstance(chave, str) or not _CHAVE_DO_JOGO.match(chave):
        return None
    if not isinstance(nome, str) or not nome.strip() or len(nome) > 200:
        return None
    if not isinstance(caminho, str) or not isinstance(titulo, str):
        return None
    titulo = titulo.strip()
    if (len(titulo) > 64 or not titulo.isprintable()
            or (titulo and molde and not re.search(molde, titulo))):
        titulo = ""
    return JogoDoLancador(chave=chave, nome=nome.strip(), instalado=True,
                          caminho=Path(caminho) if caminho else None,
                          titulo_do_jogo=titulo)


def ler_por_processo(leitor: LeitorPorProcesso, *,
                     bwrap: str | bool | None = True) -> BibliotecaDoLancador:
    """A biblioteca que o leitor da modificação devolve — e nunca levanta.

    Prazo estourado, saída grande demais, código de saída diferente de zero ou
    JSON torto: a biblioteca fica «não pôde ser lida», com o motivo numa linha,
    e o resto do censo segue. Uma linha torta dentro de uma lista boa sai
    sozinha, e as outras ficam.

    :param bwrap: ``True`` procura o ``bwrap`` no ``PATH``; um caminho usa
        aquele; ``False`` ou ``None`` roda sem caixa.
    """
    nome = leitor.rotulo
    comando = _comando_do_leitor(leitor)
    if comando is None:
        return BibliotecaDoLancador(nome, ILEGIVEL, leitor.pasta, [],
                                    ["o leitor da modificação não está na pasta dela"])
    caixa = shutil.which("bwrap") if bwrap is True else (bwrap or None)
    try:
        processo = subprocess.Popen(
            linha_do_leitor(leitor, comando, caixa), cwd=str(leitor.pasta),
            env=_ambiente_do_leitor(leitor), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True)
    except OSError as erro:
        return BibliotecaDoLancador(nome, ILEGIVEL, leitor.pasta, [], [str(erro)])
    try:
        saida, motivo = _saida_do_leitor(processo, leitor.prazo_s)
    finally:
        _parar(processo, leitor.prazo_s)
        if processo.stdout is not None:
            processo.stdout.close()
    if saida is None:
        return BibliotecaDoLancador(nome, ILEGIVEL, leitor.pasta, [], [motivo])
    try:
        bruto = json.loads(saida.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return BibliotecaDoLancador(nome, ILEGIVEL, leitor.pasta, [],
                                    ["o leitor não devolveu JSON válido"])
    if not isinstance(bruto, list) or len(bruto) > JOGOS_MAXIMOS_DO_LEITOR:
        return BibliotecaDoLancador(nome, ILEGIVEL, leitor.pasta, [],
                                    ["o leitor não devolveu uma lista de jogos"])
    jogos: dict[str, JogoDoLancador] = {}
    for linha in bruto:
        jogo = _jogo_do_leitor(linha, leitor.molde_do_titulo)
        if jogo is not None and jogo.chave not in jogos:
            jogos[jogo.chave] = jogo
    fora = sorted(jogos.values(), key=lambda j: (j.nome.casefold(), j.chave))
    ignoradas = len(bruto) - len(fora)
    erros = [f"{ignoradas} linhas do leitor não serviam"] if ignoradas else []
    return BibliotecaDoLancador(nome, LIDO, leitor.pasta, fora, erros)


def jogos_com_chave_de_janela(
    lar: Path | None = None,
) -> list[tuple[str, JogoDoLancador]]:
    """``[(lançador, jogo)]`` — só os jogos que dá para RECONHECER numa janela."""
    achados: list[tuple[str, JogoDoLancador]] = []
    for nome in _LEITORES:
        for jogo in biblioteca_de(nome, lar).jogos:
            if jogo.instalado and jogo.classe_de_janela:
                achados.append((nome, jogo))
    return achados


_FONTES: dict[str, tuple[str, ...]] = {
    "Heroic": ("store_cache/*_library.json", "store_cache/umu.json",
               *(rel for rels in _REGISTROS_DO_HEROIC.values() for rel in rels)),
    "Lutris": ("pga.db", "pga.db-wal", "games/*.yml", "runners/wine.yml",
               "runtime/umu-games/umu-games.json"),
    "RetroArch": ("playlists/*.lpl",),
    "Dolphin": ("Dolphin.ini",),
    "mGBA": ("config.ini",),
}

_FONTES_DOS_DADOS_DO_LUTRIS = ("pga.db", "pga.db-wal", "runtime/umu-games/umu-games.json")


def _impressao(caminho: Path) -> tuple[str, int, int]:
    """``(caminho, mtime_ns, tamanho)`` de um arquivo ou pasta — e nunca levanta."""
    try:
        st = os.stat(caminho)
    except OSError:
        return (str(caminho), -1, -1)
    return (str(caminho), st.st_mtime_ns, st.st_size)


def assinatura_das_bibliotecas(
    lar: Path | None = None, *,
    xdg_config: Path | None = None, xdg_data: Path | None = None,
) -> tuple[tuple[str, int, int], ...]:
    """Impressão BARATA das cinco bibliotecas — **do que se LÊ**, não da pasta."""
    linhas: list[tuple[str, int, int]] = []
    onde = _onde(lar, xdg_config, xdg_data)
    for nome in _LEITORES:
        pastas = _pastas_lidas(nome, onde)
        if not pastas:
            linhas.append((nome, -1, -1))
        for pasta in pastas:
            linhas.extend(_impressoes_da_pasta(nome, pasta, onde))
    return tuple(linhas)


def _impressoes_da_pasta(nome: str, pasta: Path, onde: _Onde) -> list[tuple[str, int, int]]:
    """A impressão de UMA pasta que o censo lê: ela e o que :data:`_FONTES` diz."""
    linhas = [_impressao(pasta)]
    for padrao in _FONTES.get(nome, ()):
        if "*" not in padrao:
            linhas.append(_impressao(pasta / padrao))
            continue
        sub, _, molde = padrao.rpartition("/")
        alvo = pasta / sub if sub else pasta
        linhas.append(_impressao(alvo))
        try:
            achados = sorted(alvo.glob(molde))
        except OSError:  # pragma: no cover - pasta ilegível
            achados = []
        linhas.extend(_impressao(a) for a in achados)
    if nome == "Lutris":
        dados = _pasta_de_dados_do_lutris(pasta, onde)
        if dados.resolve() != pasta.resolve():
            linhas.extend(_impressao(dados / rel) for rel in _FONTES_DOS_DADOS_DO_LUTRIS)
    return linhas


def sabe_ler(lancador: str) -> bool:
    """Existe leitor de biblioteca para este lançador?"""
    return lancador in _LEITORES


# -- os lançadores de fábrica: seis modificações oficiais -----------------------
#
# O que o censo, a reposição e a aba Lançadores sabem dos lançadores que vêm no pacote mora em
# `mods/de_fabrica/<chave>/hefesto-mod.json`, no MESMO bloco ``lancador`` de qualquer modificação
# (OS-SEIS-LANCADORES-VIRAM-MODIFICACOES-OFICIAIS-01). Tirar a pasta de um deles tira o lançador
# do censo, da reposição e do desenho; pôr uma pasta com outro bloco o acrescenta.
#
# Quatro campos só existem aqui e a modificação de fora não os tem (o conferidor dela os recusa
# como qualquer campo estranho): ``ordem`` (a ordem dos cartões), ``interior_lido`` (a Steam, cuja
# biblioteca o produto lê por conta própria), ``programas`` (os programas cuja biblioteca o censo
# lê, e onde) e ``reposicao`` (os processos que o reinício fecha e reabre). Os dois últimos mexem
# com arquivo do usuário e com processo dele: modificação de terceiro não escolhe isso.

NOME_DO_MANIFESTO = "hefesto-mod.json"

#: Onde moram os manifestos de fábrica; a variável existe para as réguas apontarem outra pasta.
PASTA_DE_FABRICA = Path(
    os.environ.get("HEFESTO_LANCADORES_DE_FABRICA")
    or Path(__file__).resolve().parent.parent / "mods" / "de_fabrica")

CAMPOS_SO_DE_FABRICA = frozenset({"ordem", "interior_lido", "programas", "reposicao"})

#: Os leitores de biblioteca que o censo sabe (código, não lista de lançadores): o manifesto
#: escolhe um pelo nome.
_FUNCOES_DE_LEITURA = {"heroic": _heroic, "lutris": _lutris, "retroarch": _retroarch,
                       "dolphin": _dolphin, "mgba": _mgba}


@dataclass(frozen=True)
class ProgramaDeFabrica:
    """Um programa cuja biblioteca o censo lê: o Flatpak dele, a pasta, e qual leitor."""

    nome: str
    flatpak: str
    pasta: str
    leitor: str
    #: A configuração dele cai nos dados do XDG quando não há pasta de configuração (o Lutris).
    config_nos_dados: bool = False


@dataclass(frozen=True)
class ReposicaoDeFabrica:
    """Como o reinício fecha e reabre o lançador (``reposicao_dos_lancadores``)."""

    nome: str
    processos: tuple[str, ...]
    flatpak: str | None = None
    nativo: str | None = None


@dataclass(frozen=True)
class LancadorDeFabrica:
    """Um lançador que vem no pacote: o bloco de qualquer modificação e o que é só de fábrica."""

    bloco: LancadorDaModificacao
    ordem: int
    interior_lido: bool = False
    programas: tuple[ProgramaDeFabrica, ...] = ()
    reposicao: ReposicaoDeFabrica | None = None


def _texto_de_fabrica(valor: object, onde: str) -> str:
    if not isinstance(valor, str) or not valor.strip() or len(valor) > 120:
        raise ValueError(f"«{onde}» precisa ser um texto de 1 a 120 caracteres")
    return valor.strip()


def _programa_de_fabrica(bruto: object) -> ProgramaDeFabrica:
    exigidos = {"nome", "flatpak", "pasta", "leitor"}
    if (not isinstance(bruto, dict) or not exigidos <= set(bruto)
            or set(bruto) - exigidos - {"config_nos_dados"}):
        raise ValueError("«programas» aceita só nome, flatpak, pasta, leitor e config_nos_dados")
    leitor = _texto_de_fabrica(bruto["leitor"], "programas.leitor")
    if leitor not in _FUNCOES_DE_LEITURA:
        raise ValueError(f"«programas.leitor» {leitor!r} não é um leitor que o censo sabe")
    nos_dados = bruto.get("config_nos_dados", False)
    if not isinstance(nos_dados, bool):
        raise ValueError("«programas.config_nos_dados» precisa ser verdadeiro ou falso")
    return ProgramaDeFabrica(
        nome=_texto_de_fabrica(bruto["nome"], "programas.nome"),
        flatpak=_texto_de_fabrica(bruto["flatpak"], "programas.flatpak"),
        pasta=_texto_de_fabrica(bruto["pasta"], "programas.pasta"),
        leitor=leitor, config_nos_dados=nos_dados)


def _reposicao_de_fabrica(bruto: object) -> ReposicaoDeFabrica:
    if (not isinstance(bruto, dict) or not {"nome", "processos"} <= set(bruto)
            or set(bruto) - {"nome", "processos", "flatpak", "nativo"}):
        raise ValueError("«reposicao» aceita só nome, processos, flatpak e nativo")
    processos = bruto["processos"]
    if not isinstance(processos, list) or not processos:
        raise ValueError("«reposicao.processos» precisa ser uma lista de textos")
    return ReposicaoDeFabrica(
        nome=_texto_de_fabrica(bruto["nome"], "reposicao.nome"),
        processos=tuple(_texto_de_fabrica(x, "reposicao.processos") for x in processos),
        flatpak=(_texto_de_fabrica(bruto["flatpak"], "reposicao.flatpak")
                 if "flatpak" in bruto else None),
        nativo=(_texto_de_fabrica(bruto["nativo"], "reposicao.nativo")
                if "nativo" in bruto else None))


def _lancador_de_fabrica(mod_id: str, bloco: object, pasta: Path) -> LancadorDeFabrica:
    """Confere o bloco de um manifesto de fábrica; recusa com ``ValueError``."""
    if not isinstance(bloco, dict):
        raise ValueError("«lancador» precisa ser um objeto")
    so_de_fabrica = {k: v for k, v in bloco.items() if k in CAMPOS_SO_DE_FABRICA}
    comum = lancador_da_modificacao(
        mod_id, {k: v for k, v in bloco.items() if k not in CAMPOS_SO_DE_FABRICA}, pasta)
    ordem = so_de_fabrica.get("ordem")
    if isinstance(ordem, bool) or not isinstance(ordem, int) or ordem < 0:
        raise ValueError("«lancador.ordem» precisa ser um inteiro a partir de 0")
    interior = so_de_fabrica.get("interior_lido", False)
    if not isinstance(interior, bool):
        raise ValueError("«lancador.interior_lido» precisa ser verdadeiro ou falso")
    programas = so_de_fabrica.get("programas", [])
    if not isinstance(programas, list):
        raise ValueError("«lancador.programas» precisa ser uma lista")
    return LancadorDeFabrica(
        bloco=comum, ordem=ordem, interior_lido=interior,
        programas=tuple(_programa_de_fabrica(x) for x in programas),
        reposicao=(_reposicao_de_fabrica(so_de_fabrica["reposicao"])
                   if "reposicao" in so_de_fabrica else None))


def _ler_de_fabrica(arquivo: Path) -> LancadorDeFabrica:
    try:
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        pasta = arquivo.parent
        if not isinstance(bruto, dict) or bruto.get("id") != pasta.name:
            raise ValueError("o «id» precisa ser o nome da pasta")
        if bruto.get("tipos") != ["lancador"]:
            raise ValueError("o «tipos» de um lançador de fábrica é só «lancador»")
        return _lancador_de_fabrica(pasta.name, bruto.get("lancador"), pasta)
    except (OSError, ValueError) as erro:
        raise ValueError(f"{arquivo}: {erro}") from erro


def lancadores_de_fabrica(raiz: Path | None = None) -> tuple[LancadorDeFabrica, ...]:
    """Os lançadores de fábrica de ``raiz`` (o pacote, por padrão), na ordem dos cartões.

    Pasta sem manifesto não conta, e raiz que não existe dá nenhum. Manifesto torto LEVANTA
    ``ValueError`` com o caminho: é defeito do pacote, não do disco da pessoa.
    """
    base = PASTA_DE_FABRICA if raiz is None else raiz
    try:
        pastas = sorted(p for p in base.iterdir() if p.is_dir())
    except OSError:
        return ()
    achados = [_ler_de_fabrica(p / NOME_DO_MANIFESTO) for p in pastas
               if (p / NOME_DO_MANIFESTO).is_file()]
    return tuple(sorted(achados, key=lambda f: (f.ordem, f.bloco.chave)))


#: Os lançadores de fábrica deste processo, lidos uma vez. Quem precisa de outra pasta usa
#: :func:`lancadores_de_fabrica` com ela.
DE_FABRICA: tuple[LancadorDeFabrica, ...] = lancadores_de_fabrica()

_PROGRAMAS = tuple(p for f in DE_FABRICA for p in f.programas)

#: ``{programa: (app id do Flatpak, pasta)}``.
_ONDE: dict[str, tuple[str, str]] = {p.nome: (p.flatpak, p.pasta) for p in _PROGRAMAS}

_CONFIG_CAI_NOS_DADOS = frozenset(p.nome for p in _PROGRAMAS if p.config_nos_dados)

_LEITORES = {p.nome: _FUNCOES_DE_LEITURA[p.leitor] for p in _PROGRAMAS}

#: ``{cartão da aba 07: os programas que ele junta}``. A Steam não entra: o interior dela o
#: produto lê por outro caminho.
_DO_CARTAO: dict[str, tuple[str, ...]] = {
    f.bloco.chave: tuple(p.nome for p in f.programas) for f in DE_FABRICA if not f.interior_lido}
