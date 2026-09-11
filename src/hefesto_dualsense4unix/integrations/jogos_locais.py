"""Os jogos que JÁ ESTÃO nesta máquina, para o campo "Nome do jogo:".

Pedido dela, 13/08/2026, literal: *"ou ele pré-apresenta os nomes dos jogos em
.desktop localmente instalados no pc, dessa forma ao digitar o nome do jogo ele
apareceria ali."* O campo pedia o appid cru — o número que ninguém sabe de
cabeça — e a lista é o outro lado da mesma cura: o endereço da loja
(`profiles/steam_app.steam_appid_de_texto`) cobre o jogo que ela ainda não
instalou, e esta lista cobre o que já está aqui.

**A ordem das fontes é medida, não gosto** (nesta máquina, 13/08/2026):

- ``~/.steam/steam/steamapps`` mais a biblioteca extra do `libraryfolders.vdf`
  somam **33 `appmanifest_*.acf`**, dos quais **9 são infraestrutura** (Proton,
  Steam Linux Runtime, Steamworks Common Redistributables) e **24 são jogos**;
- ``~/.local/share/applications`` tem **25 `.desktop` com `steam://rungameid/`**
  e ``/usr/share/applications`` tem **zero**.

Por isso o `.acf` vem primeiro e o `.desktop` só acrescenta o que faltar: o
`.acf` é o cadastro que a Steam mantém sozinha, com o nome COMPLETO do jogo,
enquanto o atalho `.desktop` só existe se alguém o criou e às vezes traz o nome
cortado (medido: ``Name=ORPHEUS`` para o jogo que o manifest chama
``ORPHEUS: TO HELL AND BACK``).

**Tudo local e read-only.** Nada de rede, nada de API da Steam, e nenhum
diretório além das `steamapps` de cada Steam instalada e dos `applications` que
a spec XDG declara (`pastas_de_atalhos`). Máquina sem Steam, sem `.acf` ou sem
permissão devolve lista VAZIA em silêncio — o campo continua aceitando o appid
digitado, e degradar calado aqui é requisito, não descuido.
"""
from __future__ import annotations

import configparser
import contextlib
import os
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

# O formato de linha do VDF/ACF tem UM dono neste repositório, e é o
# `steam_launch_options` — que já lê `libraryfolders.vdf` e `appmanifest_*.acf`
# para traduzir appid em nome (D-33). Importar os dois helpers de lá, mesmo
# sublinhados, é o oposto de escrever um segundo parser: um `.acf` que mude de
# escape quebraria em UM lugar, não em dois.
from hefesto_dualsense4unix.integrations.steam_launch_options import (
    _PAR_ACF,
    _desescapar_acf,
    pastas_steamapps,
)
from hefesto_dualsense4unix.profiles.steam_app import (
    parece_endereco,
    steam_appid_de_texto,
)

#: Os dois diretórios `.desktop` do pedido dela, nesta ordem — o dela primeiro,
#: porque é ele que tem os atalhos dos jogos (o do sistema tinha ZERO com
#: `rungameid` quando isto foi medido). É o PISO, não a lista: o que vale é o
#: que `pastas_de_atalhos()` devolve.
PASTAS_DE_ATALHOS: tuple[str, ...] = (
    "~/.local/share/applications",
    "/usr/share/applications",
)


def pastas_de_atalhos() -> list[Path]:
    """Os diretórios de `.desktop` DESTA máquina, na ordem da spec XDG.

    AMBIENTE-PRESUMIDO-01 (23/08/2026). A lista eram os dois caminhos acima,
    cravados — e a spec XDG diz que os `.desktop` moram em
    ``$XDG_DATA_HOME/applications`` mais um ``applications`` para cada entrada
    de ``$XDG_DATA_DIRS``. Medido nesta bancada: ``XDG_DATA_DIRS`` lista QUATRO
    diretórios, o produto olhava DOIS, e um dos dois (``/usr/share``) nem
    estava na lista da sessão. O preço foram 54 atalhos em
    ``~/.local/share/flatpak/exports/share/applications`` (todo jogo instalado
    por Flatpak) e 3 em ``/usr/local/share/applications`` que o campo "Nome do
    jogo" nunca ofereceu — sem dizer nada, porque degradar calado aqui é
    requisito.

    Os dois caminhos históricos continuam entrando mesmo que a sessão não os
    cite: um ``XDG_DATA_DIRS`` mal montado não pode ENCOLHER o que já
    funcionava. Sem repetir diretório (comparação pelo caminho real) e sem
    inventar caminho que não existe — a lista sai só com o que está em disco.
    """
    def real(caminho: Path) -> Path:
        try:
            return caminho.resolve()
        except OSError:  # pragma: no cover - link quebrado ou permissão
            return caminho

    candidatos: list[Path] = []
    data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    candidatos.append(
        Path(data_home).expanduser() / "applications"
        if data_home
        else Path("~/.local/share/applications").expanduser()
    )
    data_dirs = os.environ.get("XDG_DATA_DIRS", "").strip()
    for bruto in (data_dirs or "/usr/local/share:/usr/share").split(":"):
        limpo = bruto.strip()
        if limpo:
            candidatos.append(Path(limpo).expanduser() / "applications")
    candidatos.extend(Path(p).expanduser() for p in PASTAS_DE_ATALHOS)

    alvos: list[Path] = []
    vistos: set[Path] = set()
    for candidato in candidatos:
        if not candidato.is_dir():
            continue
        chave = real(candidato)
        if chave in vistos:
            continue
        vistos.add(chave)
        alvos.append(candidato)
    return alvos


#: `Exec=/usr/games/steam steam://rungameid/851100` — o `Exec` do atalho que a
#: própria Steam gera, e o do gerador dela (`meow-steam-<id>.desktop`).
_EXEC_RUNGAMEID_RE = re.compile(r"steam://rungameid/(\d+)", re.IGNORECASE)

#: A infraestrutura que a Steam instala como se fosse jogo. NÃO há campo no
#: `.acf` que diga "isto é ferramenta" — conferi os manifests de `Proton
#: Experimental`, `Steam Linux Runtime 3.0 (sniper)` e `Steamworks Common
#: Redistributables` contra o de `PRAGMATA` e a única diferença estrutural é o
#: `InstallScripts`, que jogo com redistribuível também tem. Então o filtro é
#: por NOME, e é declarado aqui em vez de adivinhado:
#:
#: - `Proton \d`, `Proton Experimental`, `Proton Hotfix` — e não `^Proton\b`,
#:   que esconderia um jogo chamado `Proton Pulse`;
#: - `Steam Linux Runtime …` (as quatro versões vivas nesta máquina);
#: - o nome exato do pacote de redistribuíveis.
#:
#: Nesta máquina o filtro tira 9 dos 33 manifests. Ferramenta que escape daqui
#: aparece na lista como um jogo qualquer — feio, não perigoso: escolhê-la
#: grava um appid que simplesmente nunca casa com janela nenhuma.
_FERRAMENTA_RE = re.compile(
    r"^(?:Proton (?:Experimental|Hotfix|\d)"
    r"|Steam Linux Runtime\b"
    r"|Steamworks Common Redistributables$)",
)


@dataclass(frozen=True)
class JogoLocal:
    """Um jogo achado no disco: o número, o nome e de onde veio o nome."""

    appid: str
    nome: str
    #: ``"steam"`` (veio de um `appmanifest_*.acf`), ``"desktop"``, ou o nome do
    #: lançador em minúsculas (``"heroic"``) — JOGOS-DOS-LANCADORES-01.
    fonte: str
    #: O LANÇADOR de onde ele veio, como a tela o escreve (``"Heroic"``). Vazio
    #: para a Steam, que é a fonte que já tinha nome próprio nos dois rótulos.
    lancador: str = ""
    #: A `wm_class` que a janela dele anuncia (``"gotg.exe"``). Vazia na Steam,
    #: que endereça por `appid`. **Um dos dois sempre existe** — ver `valor`.
    chave: str = ""

    @property
    def rotulo(self) -> str:
        """Como ele aparece na lista da completação: nome e endereço juntos.

        O número NÃO some do rótulo pelo mesmo motivo que ele não some de
        `steam_launch_options.rotulo_do_jogo`: é o que ela confere na Steam, e
        é o único identificador que os cadastros do projeto compartilham.

        **O JOGO DE LANÇADOR DIZ O LANÇADOR, e não a chave** — 10/09/2026. A
        chave dele é o nome do binário (``gotg.exe``), que não é um dado que
        ela confira em lugar nenhum; o que responde *"de onde vem este jogo?"*
        é o nome do programa que o instalou, e é o que o desenho da coluna
        «Quando usar» já escreve (*«Jogo · mk1.exe»*, *«Jogo da Steam · …»*).
        """
        if self.lancador:
            return f"{self.nome} ({self.lancador})"
        return f"{self.nome} (appid {self.appid})"

    @property
    def valor(self) -> str:
        """O que o CAMPO grava quando ela escolhe esta linha.

        É a metade que o `<datalist>` põe no `value`, e trocá-la por outra
        coisa é o defeito que a régua da lista já guarda: escrever o NOME faria
        nascer um `steam_app_Sea of Stars`, que nunca casa com janela nenhuma.
        """
        return self.chave or self.appid

    @property
    def forma(self) -> str:
        """A chave de `simple_match.from_simple_choice` para esta linha.

        ``"steam_game"`` guarda ``steam_app_<id>``; ``"janela"`` guarda a
        `wm_class` crua — a sexta forma, nascida na ONDA5-10-01 para o jogo de
        fora da Steam. **São o MESMO campo do perfil** (`window_class`), que é
        o que o critério de pronto desta sprint exige: *"nunca um campo novo"*.
        """
        return "janela" if self.chave else "steam_game"


def e_ferramenta_da_steam(nome: str) -> bool:
    """O `.acf` é de infraestrutura (Proton, runtime, redistribuíveis)?"""
    return _FERRAMENTA_RE.match(nome.strip()) is not None


def chave_de_busca(texto: str) -> str:
    """Texto achatado para comparar: sem acento, sem caixa, sem espaço em volta.

    ``"Sackboy\u2122: A Big Adventure"`` e ``"sackboy"`` têm de se encontrar,
    e o símbolo vai escapado de propósito: o ADR-011 recusa o glifo cru, e
    ele é parte do nome que a Steam grava no `appmanifest`. ``"Pokémon"`` tem de
    casar com ``"pokemon"`` — ela digita no teclado dela, não no do catálogo.
    """
    decomposto = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.casefold().strip()


def _campos_do_acf(texto: str) -> dict[str, str]:
    """Os pares `"chave" "valor"` de PRIMEIRO nível úteis aqui (appid, name).

    Rasteiro de propósito: um `.acf` é uma árvore, mas `appid` e `name` moram
    na raiz e as subseções (`InstalledDepots`, `UserConfig`) não têm chave com
    esses nomes. Ler a árvore inteira para tirar dois campos seria um segundo
    parser de VDF no repositório.
    """
    campos: dict[str, str] = {}
    for linha in texto.splitlines():
        par = _PAR_ACF.match(linha)
        if par is None:
            continue
        chave = par.group("chave").lower()
        if chave in {"appid", "name"} and chave not in campos:
            campos[chave] = _desescapar_acf(par.group("valor")).strip()
    return campos


def jogos_da_biblioteca_steam(home: Path | None = None) -> list[JogoLocal]:
    """Os jogos dos `appmanifest_*.acf`, de toda biblioteca configurada.

    Best-effort inteiro: pasta ilegível, manifest truncado ou sem `name` são
    pulados sem levantar — quem chama é a montagem de uma lista de sugestão.

    A deduplicação por caminho RESOLVIDO não é ornamento: nesta máquina o
    `libraryfolders.vdf` aponta para ``~/.steam/debian-installation``, que é
    para onde ``~/.steam/steam`` aponta — sem `resolve()` a mesma biblioteca
    seria varrida duas vezes.
    """
    vistas: set[Path] = set()
    achados: dict[str, JogoLocal] = {}
    for pasta in pastas_steamapps(home):
        real = pasta
        with contextlib.suppress(OSError):
            real = pasta.resolve()
        if real in vistas:
            continue
        vistas.add(real)
        try:
            manifests = sorted(real.glob("appmanifest_*.acf"))
        except OSError:
            continue
        for manifesto in manifests:
            try:
                texto = manifesto.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            campos = _campos_do_acf(texto)
            appid = campos.get("appid", "")
            nome = campos.get("name", "")
            if not appid.isdigit() or not nome:
                continue
            if e_ferramenta_da_steam(nome):
                continue
            achados.setdefault(appid, JogoLocal(appid=appid, nome=nome, fonte="steam"))
    return list(achados.values())


def assinatura_da_biblioteca(home: Path | None = None) -> tuple[tuple[str, int], ...]:
    """Impressão BARATA da biblioteca: ``(pasta, mtime_ns)`` de cada `steamapps`.

    Existe para uma pergunta só, e ela se repete: *"instalaram ou tiraram jogo
    desde a última vez que eu olhei?"*. Ler os 33 `appmanifest_*.acf` para
    responder isso custaria 33 aberturas de arquivo; dois `stat()` de diretório
    custam microssegundos, e o `mtime` de um diretório MUDA quando um arquivo
    nasce ou morre dentro dele — que é exatamente o que instalar e desinstalar
    um jogo fazem com a `steamapps`.

    Pasta ausente entra com ``-1`` em vez de sumir da lista: instalar a Steam
    depois também tem de contar como mudança. Pasta ilegível idem — não saber
    é diferente de saber que não mudou.

    NÃO responde "que jogos são" — para isso é `jogos_da_biblioteca_steam`.
    Esta é o freio que decide se vale a pena chamar aquela.
    """
    linhas: list[tuple[str, int]] = []
    for pasta in pastas_steamapps(home):
        try:
            linhas.append((str(pasta), os.stat(pasta).st_mtime_ns))
        except OSError:
            linhas.append((str(pasta), -1))
    return tuple(linhas)


def _nome_do_desktop(texto: str) -> str:
    """O `Name=` do grupo `[Desktop Entry]`, sem as variantes de idioma.

    ``Name[pt_BR]=`` fica de fora: a lista é comparada com o que ela digita, e
    misturar duas grafias do mesmo jogo dobraria a linha na completação.
    """
    for linha in texto.splitlines():
        crua = linha.strip()
        if crua.startswith("Name="):
            return crua[len("Name=") :].strip()
    return ""


#: AS CATEGORIAS QUE FAZEM DE UM `.desktop` UM LANÇADOR — LANCADOR-ACHADO-01,
#: 09/09/2026, degrau 2: *"procurar pelo que a coisa É, não pelo nome que ela
#: tem"*.
#:
#: **`Game` SOZINHO NÃO BASTA, e a medição na máquina dela diz por quê:** dos
#: 23 `.desktop` com `Categories=Game` em `~/.local/share/applications`, a
#: grande maioria são JOGOS instalados, não lançadores. Um cartão por jogo na
#: aba Lançadores seria uma lista de 23 cartões onde ela espera seis.
#:
#: O QUE SEPARA UM LANÇADOR DE UM JOGO é a segunda categoria, e ela é
#: declarada pelo próprio programa: `PackageManager` (o Heroic e o Lutris
#: INSTALAM jogos) ou `Emulator` (o RetroArch, o Dolphin e o mGBA RODAM jogos
#: de outra plataforma). Medido nos sete `Game` do flatpak dela::
#:
#:     org.DolphinEmu.dolphin-emu   Game;Emulator;        -> lançador
#:     io.mgba.mGBA                 Game;Emulator;        -> lançador
#:     org.libretro.RetroArch       Game;Emulator;        -> lançador
#:     com.heroicgameslauncher.hgl  Game;PackageManager;  -> lançador
#:     net.lutris.Lutris            Game;PackageManager;  -> lançador
#:     io.github.dummerle.rare      Game;                 -> não decide
#:     net.davidotek.pupgui2        Game;Utility;         -> não decide
#:
#: **OS CINCO DA LISTA APARECEM SOZINHOS**, sem que ninguém digite o nome
#: deles — que é a entrega inteira do degrau 2.
_CATEGORIAS_DE_LANCADOR = frozenset({"PackageManager", "Emulator"})

#: A ARMADILHA MEDIDA, e ela é por que a comparação é por TOKEN e nunca por
#: substring: `debian-uxterm` declara `Categories=System;TerminalEmulator;`, e
#: `"Emulator" in texto` o transformaria num lançador de jogos. Estão os dois
#: na máquina dela hoje.
#:
#: A spec XDG diz que `Categories` é uma lista separada por `;` — então o que
#: se compara é o item da lista, inteiro.
_NAO_E_JOGO = frozenset({"TerminalEmulator"})


def _campo_do_desktop(texto: str, campo: str) -> str:
    """O valor de `campo=` no `.desktop`, sem as variantes de idioma.

    É o irmão de `_nome_do_desktop`, generalizado — e ele nasceu junto com o
    degrau 2, que precisa de `Categories` e `NoDisplay` além do `Name`.
    """
    alvo = f"{campo}="
    for linha in texto.splitlines():
        crua = linha.strip()
        if crua.startswith(alvo):
            return crua[len(alvo):].strip()
    return ""


def _categorias(texto: str) -> frozenset[str]:
    """As `Categories` deste `.desktop`, como CONJUNTO de itens inteiros."""
    cru = _campo_do_desktop(texto, "Categories")
    return frozenset(p.strip() for p in cru.split(";") if p.strip())


def e_lancador_de_jogos(texto: str) -> bool:
    """Este `.desktop` se declara um lançador de jogos?

    **LANCADOR-ACHADO-01, degrau 2.** A pergunta que o produto fazia era
    *"existe um arquivo com este nome?"* — cinco strings que alguém digitou —,
    e tudo que não batia sumia da tela com um `NÃO LOCALIZADO` sobre um
    programa instalado e funcionando. A palavra dela foi *"isso é uma falha de
    produto e a culpa é minha"*, e **a culpa não é dela**: o produto que exige
    a forma certa de instalar terceiriza para quem usa uma pergunta que ele
    mesmo deveria responder.

    A pergunta agora é sobre o MUNDO: *"existe um programa que declara fazer
    isso?"* — que é exatamente a pergunta que o cartão do Flatpak já fazia, e
    a assimetria que a §2 da sprint nomeia.

    O QUE ISSO ALCANÇA SOZINHO: o `net.lutris.Lutris-beta`, o AppImage que
    publica `.desktop`, o snap, o pacote compilado em `/opt` e o emulador que
    ninguém previu. O que ele **não** alcança é o AppImage solto, que não
    publica nada — e esse é o degrau 3, o registro à mão.

    `NoDisplay=true` FICA DE FORA: é o que a spec usa para dizer *"não me
    mostre no menu"*, e um lançador escondido do menu dela não é um cartão.
    """
    cats = _categorias(texto)
    if cats & _NAO_E_JOGO:
        return False
    if "Game" not in cats:
        return False
    if _campo_do_desktop(texto, "NoDisplay").lower() == "true":
        return False
    return bool(cats & _CATEGORIAS_DE_LANCADOR)


def lancadores_por_conteudo(
    pastas: Sequence[Path] | None = None,
) -> dict[str, str]:
    """`{stem do .desktop: Name=}` de todo lançador de jogos DESTA máquina.

    **A CHAVE É O `stem`** porque é o que `_onde_estao_os_lancadores` já casa
    contra os `atalhos` do `SemCenso` — assim o achado por conteúdo entra na
    aba pelo caminho que já existe, sem uma segunda rota de identidade.

    NUNCA LEVANTA: um `.desktop` ilegível é pulado. Esta função é chamada na
    montagem da aba, e uma exceção aqui apagaria a grade inteira por um
    arquivo com byte torto.

    A ORDEM DAS PASTAS É A DA SPEC (`pastas_de_atalhos`), e o PRIMEIRO nome
    vence: `~/.local/share` sobrepõe `/usr/share`, que é o que a XDG manda.
    """
    achados: dict[str, str] = {}
    for pasta in (pastas if pastas is not None else pastas_de_atalhos()):
        try:
            arquivos = sorted(pasta.glob("*.desktop"))
        except OSError:  # pragma: no cover - pasta some entre o listar e o ler
            continue
        for arq in arquivos:
            if arq.stem in achados:
                continue
            try:
                texto = arq.read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover
                continue
            if e_lancador_de_jogos(texto):
                achados[arq.stem] = _nome_do_desktop(texto) or arq.stem
    return achados


def jogos_dos_atalhos_desktop(
    pastas: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """Os jogos dos `.desktop` que apontam para `steam://rungameid/<id>`.

    Lê `Exec=` e também `X-SteamAppId=`, que é o campo que o gerador dela
    escreve (medido em `meow-steam-851100.desktop`). `NoDisplay=true` é pulado:
    o atalho que o menu não mostra também não deve entrar na lista dela.
    """
    alvos = list(pastas) if pastas is not None else pastas_de_atalhos()
    achados: dict[str, JogoLocal] = {}
    for pasta in alvos:
        try:
            arquivos = sorted(pasta.glob("*.desktop"))
        except OSError:
            continue
        for arquivo in arquivos:
            try:
                texto = arquivo.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "NoDisplay=true" in texto:
                continue
            achado = _EXEC_RUNGAMEID_RE.search(texto)
            appid = achado.group(1) if achado is not None else ""
            if not appid:
                for linha in texto.splitlines():
                    if linha.strip().startswith("X-SteamAppId="):
                        appid = linha.split("=", 1)[1].strip()
                        break
            if not appid.isdigit():
                continue
            nome = _nome_do_desktop(texto)
            if not nome:
                continue
            achados.setdefault(
                appid, JogoLocal(appid=appid, nome=nome, fonte="desktop")
            )
    return list(achados.values())


def catalogo_de_jogos(
    home: Path | None = None,
    pastas_de_atalhos: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """As duas fontes juntas, em ordem alfabética e sem appid repetido.

    A biblioteca Steam ganha o desempate — ela é o cadastro que a Steam mantém
    sozinha, e o nome dela é o completo (o atalho já foi medido cortando
    ``ORPHEUS: TO HELL AND BACK`` em ``ORPHEUS``).
    """
    por_appid: dict[str, JogoLocal] = {}
    for jogo in jogos_da_biblioteca_steam(home):
        por_appid.setdefault(jogo.appid, jogo)
    for jogo in jogos_dos_atalhos_desktop(pastas_de_atalhos):
        por_appid.setdefault(jogo.appid, jogo)
    return sorted(por_appid.values(), key=lambda j: (chave_de_busca(j.nome), j.appid))


def jogos_dos_lancadores(lar: Path | None = None) -> list[JogoLocal]:
    """A SEGUNDA ORIGEM — os jogos dos cinco lançadores que não são a Steam.

    **JOGOS-DOS-LANCADORES-01, 10/09/2026.** A frase dela era *"cada um dos
    lançadores passarem a ter os jogos com perfis dentro da aba perfis"*, e o
    que o produto tinha era uma origem só: a Steam.  # noqa-acento: citação dela

    **SÓ ENTRA QUEM TEM ENDEREÇO.** `censo_dos_lancadores.jogos_com_chave_de_janela`
    é quem decide, e a docstring dele diz o preço da alternativa: uma linha sem
    chave é uma linha que nunca casa com janela nenhuma (R-12). Isto **não** é
    a decisão (A)/(B) da §3 da sprint — aquela é sobre a LISTA DE PERFIS
    crescer sozinha, e é dela; esta é a lista de SUGESTÃO do campo, que é o (C)
    que ela já tem, e que não cria linha nenhuma sem ela pedir.

    O `appid` sai VAZIO de propósito: um jogo de fora da Steam não tem appid, e
    inventar um número nosso obrigaria a traduzir nos dois sentidos para
    sempre — é o mesmo argumento que `JogoDoLancador.chave` já carrega.

    NUNCA LEVANTA: `biblioteca_de` promete não levantar, e quem chama é a
    pintura de uma aba.

    :param lar: o `HOME` a inspecionar. Uma régua passa um lar de mentira — e
        **nenhuma régua desta sprint depende de a máquina ter Heroic**.
    """
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
        jogos_com_chave_de_janela,
    )

    achados: dict[str, JogoLocal] = {}
    for lancador, jogo in jogos_com_chave_de_janela(lar):
        classe = jogo.classe_de_janela
        achados.setdefault(classe, JogoLocal(
            appid="", nome=jogo.nome, fonte=lancador.casefold(),
            lancador=lancador, chave=classe))
    return sorted(achados.values(), key=lambda j: (chave_de_busca(j.nome), j.chave))


#: O `.desktop` de um LANÇADOR não é um jogo. `Game;PackageManager;` é como o
#: Heroic e o Lutris se declaram — são a loja, e um perfil para a vitrine não é
#: o que ela pediu. `Game;Emulator;` FICA, e é DECISÃO com razão escrita, não
#: descuido: ver o bloco «POR QUE O EMULADOR FICA», logo abaixo.
_CATEGORIA_QUE_NAO_E_JOGO = "packagemanager"

#: **O CLIENTE DE LOJA QUE NÃO SE DECLARA COMO TAL.** `Categories` é o filtro
#: certo e resolve Heroic e Lutris, que escrevem `PackageManager`. O Rare —
#: cliente alternativo da Epic — **não escreve**. Medido no `.desktop` dele em
#: 11/09/2026, `…/flatpak/exports/share/applications/io.github.dummerle.rare`::
#:
#:     Categories=Game;
#:     StartupWMClass=rare
#:     Comment=Open source alternative for Epic Games Launcher, using Legendary
#:
#: … e não há campo que o separe de um jogo. Então ele é declarado aqui, pelo
#: mesmo argumento que `_FERRAMENTA_RE` já carrega para a infraestrutura da
#: Steam: um filtro POR NOME, ESCRITO, é melhor que adivinhar. E o preço de
#: deixá-lo entrar era concreto — a biblioteca que o Rare abre é a MESMA que
#: `censo_dos_lancadores._heroic` já lê pelo `legendary_library.json`, jogo por
#: jogo: ele ofereceria a VITRINE da Epic no campo «Nome do Jogo», ao lado dos
#: jogos dela.
_CLIENTES_DE_LOJA = frozenset({"rare"})

# **POR QUE O EMULADOR FICA, e isto é DECISÃO — 11/09/2026.** Os quatro que a
# máquina dela tem (`azahar`, `mGBA`, `retroarch`, `SUPERZSNES`) declaram
# `Game;Emulator;`, e `e_lancador_de_jogos` os chama de LANÇADOR na aba 07.
# Aqui eles entram assim mesmo, e a razão é a §4 da sprint: um emulador é UM
# processo para todas as ROMs, então **a janela do emulador é a única janela
# que existe**. Um perfil mirando `SUPERZSNES` é o perfil daquele console; um
# perfil mirando `240pSuite.sfc` seria uma regra que nunca casa (R-12).
#
# **O QUE ISSO NÃO É: um jogo achado.** Nesta origem, no disco dela hoje, o
# número de JOGOS é ZERO — os cinco achados eram quatro emuladores mais o
# Rare, que agora sai. Quem prova o motor desta sprint é o Heroic (`gotg.exe`
# → *Marvel's Guardians of the Galaxy*), e esta origem existe para o dia em
# que ela puser um jogo no menu — que é o caso do `.desktop` escrito à mão.

#: O rótulo do lançador para um jogo que não veio de lançador nenhum. Aparece
#: na lista (``"Celeste (Instalado aqui)"``) e é o que responde *"de onde vem
#: este?"* — a única resposta honesta quando a resposta é "de lugar nenhum,
#: está no menu".
LANCADOR_DIRETO = "Instalado aqui"


def jogos_diretos_dos_atalhos(
    pastas: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """A TERCEIRA ORIGEM — o jogo que não é de lançador nenhum, pelo `.desktop`.

    **`StartupWMClass=` É A ETIQUETA, e ela não é invenção nossa**: é o campo
    da spec XDG com que o compositor liga uma janela ao atalho que a abriu —
    exatamente a pergunta que o perfil faz. Medido nas quatro pastas XDG dela
    em 11/09/2026:

        221 `.desktop` · 59 com `StartupWMClass` · 31 com `Categories=Game`

    e dos 31, **23 são os `meow-steam-*.desktop` dela, que escrevem
    ``StartupWMClass=steam_app_<id>``** — a prova de que este campo é o MESMO
    endereço que o perfil da Steam já guarda, e não um segundo cadastro.

    **OS `steam_app_<id>` SAEM DAQUI**, e não por serem inúteis: são a origem
    da Steam, que `catalogo_de_jogos` já lê com o nome COMPLETO do `.acf`
    (o atalho já foi medido cortando ``ORPHEUS: TO HELL AND BACK`` em
    ``ORPHEUS``). Deixá-los entrar seria a mesma linha duas vezes, uma delas
    com o nome pior.

    **E OS LANÇADORES SAEM PELO QUE ELES MESMOS DECLARAM** —
    `Categories` com `PackageManager` (ver `_CATEGORIA_QUE_NAO_E_JOGO`). Sem
    isso, Heroic e Lutris entrariam na lista de JOGOS da aba Perfis. **O Rare
    não se declara** e sai por `_CLIENTES_DE_LOJA`, que diz por quê.

    **O QUE ELA ACHA NO DISCO DELA HOJE, medido em 11/09/2026 e corrigindo o
    que esta entrega publicou primeiro: ZERO jogos.** Os cinco `.desktop` que
    passam pelos filtros são quatro EMULADORES (`azahar`, `mGBA`, `retroarch`,
    `SUPERZSNES`) mais o `rare`, que agora sai. Os emuladores ficam por
    decisão escrita — a janela deles é a única que existe —, e **isso não os
    torna jogos achados**: quem prova o motor desta sprint é o Heroic
    (``gotg.exe`` → *Marvel's Guardians of the Galaxy*), que é o exemplo da
    queixa dela. Esta origem existe para o jogo posto no menu à mão, e o
    número dela hoje é honesto: zero.

    NUNCA LEVANTA, e devolve lista vazia em silêncio numa máquina sem atalho
    nenhum — o mesmo contrato de `jogos_dos_atalhos_desktop`, logo acima.
    """
    alvos = list(pastas) if pastas is not None else pastas_de_atalhos()
    achados: dict[str, JogoLocal] = {}
    for pasta in alvos:
        try:
            arquivos = sorted(pasta.glob("*.desktop"))
        except OSError:
            continue
        for arquivo in arquivos:
            try:
                texto = arquivo.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            cfg = configparser.ConfigParser(strict=False, interpolation=None)
            try:
                cfg.read_string(texto)
            except configparser.Error:
                continue
            if not cfg.has_section("Desktop Entry"):
                continue
            entrada = cfg["Desktop Entry"]
            if entrada.get("NoDisplay", "").strip().casefold() == "true":
                continue
            classe = entrada.get("StartupWMClass", "").strip()
            categorias = {c.strip().casefold()
                          for c in entrada.get("Categories", "").split(";")}
            if not classe or "game" not in categorias:
                continue
            if _CATEGORIA_QUE_NAO_E_JOGO in categorias:
                continue
            if classe.casefold() in _CLIENTES_DE_LOJA:
                continue
            if steam_appid_de_texto(classe) is not None:
                continue
            nome = _nome_do_desktop(texto)
            if not nome:
                continue
            achados.setdefault(classe, JogoLocal(
                appid="", nome=nome, fonte="desktop",
                lancador=LANCADOR_DIRETO, chave=classe))
    return sorted(achados.values(), key=lambda j: (chave_de_busca(j.nome), j.chave))


def jogos_com_janela(
    lar: Path | None = None,
    pastas: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """**AS TRÊS ORIGENS DE FORA DA STEAM, numa lista só** — o motor da sprint.

    Heroic, Lutris (`jogos_dos_lancadores`) e o jogo direto do menu
    (`jogos_diretos_dos_atalhos`), cada um com a `chave` que a janela dele
    anuncia. **Quem vem de lançador ganha o desempate**: ele sabe o nome da
    loja, e o `.desktop` às vezes traz o nome do atalho e não o do jogo.

    É a lista que `jogo_da_janela` procura e que `nomes_das_janelas` indexa.
    """
    jogos = list(jogos_dos_lancadores(lar))
    vistos = {j.chave.casefold() for j in jogos}
    jogos += [j for j in jogos_diretos_dos_atalhos(pastas)
              if j.chave.casefold() not in vistos]
    return sorted(jogos, key=lambda j: (chave_de_busca(j.nome), j.chave))


def jogo_da_janela(
    classe: str | None,
    jogos: Iterable[JogoLocal],
) -> JogoLocal | None:
    """**A FUNÇÃO QUE O «DETECTAR» PRECISAVA**: de uma `wm_class`, QUE JOGO É.

    É a volta do caminho que `steam_appid_from_wm_class` já fazia para a
    Steam, e ela é a falta que ELA nomeou em 11/09/2026, com a foto na mão:
    o botão «Detectar» responde ``PRAGMATA`` para ``steam_app_3357650`` e
    **não responde nada** para um jogo que não é da Steam —
    *"em perfil falta detectar os jogos dos demais lançadores"*.

    O botão SEMPRE GRAVOU a regra certa para o jogo de fora da Steam (a forma
    "janela", ONDA5-10-01): o que faltava não era a regra, era o NOME. Sem
    ele o desfecho diz *"«Perfil» agora vale em: Só neste programa"* sobre
    uma `wm_class` que ela não digitou, vinda de uma janela que ela não está
    mais olhando — que é a mesma coisa que não achar.

    PURA: recebe a lista já lida (`jogos_com_janela`), para que a régua não
    precise da biblioteca dela. Quem lê o disco é `nomes_das_janelas`.

    **A COMPARAÇÃO É INSENSÍVEL A CAIXA, e isso é medido e não gosto:** o
    `pga.db` dela guarda ``/home/x/Games/gotg/GOTG.exe`` e a janela do mesmo
    jogo pelo Heroic anuncia ``gotg.exe``. Exigir caixa igual faria o mesmo
    jogo não se reconhecer conforme o lançador por onde ela o abriu.

    `steam_app_<id>` devolve `None` de propósito: ele tem dono, e o dono é
    `catalogo_de_jogos` pelo appid. Duas respostas para o mesmo endereço é a
    segunda verdade que esta casa já pagou.
    """
    alvo = (classe or "").strip().casefold()
    if not alvo or alvo == "unknown":
        return None
    for jogo in jogos:
        if jogo.chave and jogo.chave.casefold() == alvo:
            return jogo
    return None


#: O caderno das três origens: `(assinatura, [JogoLocal], {wm_class: nome})`.
#:
#: **UM CADERNO PARA AS DUAS FORMAS, e não dois.** A tela precisa das duas — a
#: LISTA para oferecer no `<datalist>` e para perguntar a FORMA da regra
#: (`JogoLocal.forma`), e o DICIONÁRIO para o rótulo consultar em O(1) dez
#: vezes por segundo. Dois cadernos seriam duas leituras do mesmo `pga.db` e
#: dos mesmos 221 `.desktop`, e dois caminhos de invalidação para uma verdade
#: só — que é a forma exata do defeito que esta casa nomeia toda semana.
_NOMES_DAS_JANELAS: tuple[object, list[JogoLocal], dict[str, str]] | None = None


def assinatura_das_janelas(
    lar: Path | None = None,
    pastas: Sequence[Path] | None = None,
) -> tuple[object, ...]:
    """Impressão BARATA das três origens de fora da Steam — o freio do caderno.

    Mesmo molde de `assinatura_da_biblioteca` e pela mesma razão: responder
    *"mudou alguma coisa desde a última vez?"* com `stat()` barato, em vez de
    reabrir o `pga.db` e os 221 `.desktop` dez vezes por segundo.

    **O QUE A METADE DOS LANÇADORES ASSINA É O ARQUIVO, e isso é de
    11/09/2026:** `assinatura_das_bibliotecas` assinava a pasta de cima e
    nunca invalidava para o Heroic — ver `censo_dos_lancadores._FONTES`. A
    metade dos `.desktop` continua sendo o `mtime` da PASTA, e aqui isso é o
    certo: instalar, desinstalar ou atualizar um programa CRIA, APAGA ou
    renomeia um arquivo dentro da pasta, e é isso que o `mtime` de um
    diretório enxerga.

    O QUE ELA NÃO ALCANÇA, declarado em vez de adivinhado: um `.desktop` que
    já existe EDITADO no lugar (alguém acrescentando `StartupWMClass=` à mão)
    não muda o `mtime` da pasta. Assiná-los um a um custaria 221 `stat()` por
    tique, dez vezes por segundo, para cobrir um caso que nenhum instalador
    produz — eles escrevem em arquivo temporário e renomeiam, o que a pasta
    vê. O degrau, se ele aparecer, é acrescentar os arquivos aqui, como
    `censo_dos_lancadores._FONTES` faz do outro lado.

    **AS DUAS METADES SÃO PRECISAS SEPARADAS:** as cinco pastas de lançador
    vêm de `censo_dos_lancadores.assinatura_das_bibliotecas`, e as pastas de
    `.desktop` entram aqui — somá-las numa assinatura só faria a lista do
    Heroic ser relida toda vez que um flatpak qualquer instalasse um atalho,
    mas separá-las em dois cadernos custaria dois caminhos de invalidação para
    uma lista só. Um caderno, uma assinatura que soma as duas.
    """
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
        assinatura_das_bibliotecas,
    )

    linhas: list[object] = [assinatura_das_bibliotecas(lar)]
    alvos = list(pastas) if pastas is not None else pastas_de_atalhos()
    for pasta in alvos:
        try:
            linhas.append((str(pasta), os.stat(pasta).st_mtime_ns))
        except OSError:
            linhas.append((str(pasta), -1))
    return tuple(linhas)


def _caderno_das_janelas(
    lar: Path | None,
    pastas: Sequence[Path] | None,
) -> tuple[list[JogoLocal], dict[str, str]]:
    """A leitura das três origens, memoizada — a LISTA e o índice, de uma vez.

    **NUNCA LEVANTA.** Quem chama é a aba Perfis, que é PINTURA — dez vezes
    por segundo. Uma exceção lendo o `pga.db` do Lutris derrubaria a aba
    inteira por causa de um rótulo, que é o contrato que
    `a10_perfis._jogo_reconhecido` já declara.

    O ÍNDICE ENTRA EM MINÚSCULAS, e a lista guarda a caixa do disco: quem
    consulta o índice direto (`frase_do_campo_do_jogo`) não pode depender de
    ela ter aberto o jogo pelo Heroic (``gotg.exe``) ou pelo Lutris
    (``GOTG.exe``); quem varre a lista é `jogo_da_janela`, que dobra os dois
    lados sozinho.
    """
    global _NOMES_DAS_JANELAS
    try:
        assinatura = assinatura_das_janelas(lar, pastas)
        if _NOMES_DAS_JANELAS is not None and _NOMES_DAS_JANELAS[0] == assinatura:
            return _NOMES_DAS_JANELAS[1], _NOMES_DAS_JANELAS[2]
        jogos = list(jogos_com_janela(lar, pastas))
    except Exception:  # pragma: no cover - disco hostil; ver o contrato acima
        return [], {}
    nomes = {j.chave.casefold(): j.nome for j in jogos if j.chave}
    _NOMES_DAS_JANELAS = (assinatura, jogos, nomes)
    return jogos, nomes


def nomes_das_janelas(
    lar: Path | None = None,
    pastas: Sequence[Path] | None = None,
) -> dict[str, str]:
    """``{wm_class: nome}`` das três origens — **o que o RÓTULO consulta**.

    É a metade que lê o disco, separada de `jogo_da_janela` (que é pura) pela
    mesma disciplina de `_nomes_dos_jogos` na aba: a leitura é memoizada pela
    assinatura, e a decisão fica testável sem a biblioteca dela.

    Entra como terceiro argumento de `frase_do_campo_do_jogo`, que é a quinta
    resposta do rótulo ao lado do campo «Nome do Jogo»
    (`a10_perfis._jogo_reconhecido`). Nunca levanta — ver `_caderno_das_janelas`.
    """
    return _caderno_das_janelas(lar, pastas)[1]


def jogos_de_janela(
    lar: Path | None = None,
    pastas: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """A MESMA leitura na forma de LISTA — o que o `<datalist>` oferece.

    Duas perguntas da tela precisam do `JogoLocal` inteiro, e não só do nome:

    * **o que oferecer** no campo «Nome do Jogo» — `JogoLocal.rotulo` diz o
      lançador (*"(Heroic)"*) e `JogoLocal.valor` diz o que o campo grava;
    * **que FORMA de regra** o texto escolhido pede — `JogoLocal.forma`, que é
      o que `a10_perfis._forma_do_que_ela_escolheu` pergunta antes de gravar.
      Sem ela a `wm_class` que a própria lista ofereceu era gravada como
      `process_name`, que é outro dado e casa por acaso (medido na tela viva
      em 10/09/2026).

    Mesmo caderno de `nomes_das_janelas`, então chamar as duas no mesmo tique
    custa UMA leitura de disco. Nunca levanta.
    """
    return _caderno_das_janelas(lar, pastas)[0]


def ofertas_do_campo_do_jogo(
    da_steam: Iterable[JogoLocal],
    dos_lancadores: Iterable[JogoLocal],
) -> list[JogoLocal]:
    """AS DUAS ORIGENS JUNTAS — o que o campo «Nome do Jogo» oferece.

    A Steam (`catalogo_de_jogos`) e os lançadores (`jogos_dos_lancadores`), em
    ordem alfabética pelo NOME, que é o que ela procura — nunca pelo endereço.

    **RECEBE AS DUAS LISTAS, e não as lê do disco**, porque quem chama é a
    PINTURA da aba Perfis, dez vezes por segundo: ela já guarda cada origem
    memoizada pela assinatura da sua biblioteca, e ler aqui de novo seria pagar
    duas vezes o que está na mão. O que sobra é a JUNÇÃO — que é o que precisa
    ter um dono só: escrevê-la também dentro do pacote da aba seria a segunda
    verdade sobre qual jogo a lista oferece.

    **`catalogo_de_jogos` NÃO FOI ALARGADO, e a razão é de contrato**: o dono
    dele promete *"sem appid repetido"* e `nomes_por_appid` indexa por appid.
    Um jogo de lançador tem `appid=""`; enfiá-lo ali faria os 29 do Heroic
    colapsarem numa única entrada de chave vazia, e levaria a mudança para
    dentro de um chamador que não é desta sprint (`profiles_actions`, que enche
    o `Gtk.EntryCompletion`).

    **A DESEMPATE É DA STEAM**, pelo mesmo motivo de sempre: se o mesmo jogo
    aparecer nas duas origens, o número é o endereço que o produto inteiro já
    compartilha.
    """
    jogos = list(da_steam)
    vistos = {chave_de_busca(j.nome) for j in jogos}
    jogos += [j for j in dos_lancadores
              if chave_de_busca(j.nome) not in vistos]
    return sorted(jogos, key=lambda j: (chave_de_busca(j.nome), j.valor))


def nomes_por_appid(jogos: Iterable[JogoLocal]) -> dict[str, str]:
    """``{"851100": "Touhou Luna Nights"}`` — o que a frase da tela consulta."""
    return {jogo.appid: jogo.nome for jogo in jogos}


def casa_com_o_que_ela_digitou(jogo: JogoLocal, digitado: str) -> bool:
    """A linha entra na lista suspensa para este texto?

    Casa por PEDAÇO do nome (``"sea"`` acha ``"Sea of Stars"``, e ``"stars"``
    também) e por começo do ENDEREÇO — depois de escolher um jogo o campo fica
    com o appid (ou com a `wm_class`, num jogo de lançador), e é isso que ela
    tem na frente para conferir.
    """
    chave = chave_de_busca(digitado)
    if not chave:
        return False
    endereco = chave_de_busca(jogo.valor)
    return chave in chave_de_busca(jogo.nome) or endereco.startswith(chave)


#: A frase que a janela mostra quando o texto colado não é jogo nenhum. Fica
#: aqui, e não no editor, porque ela é o resultado de uma decisão PURA e
#: testável sem GTK — mesmo molde de `texto_do_processo_que_nao_casa`.
#:
#: CURTA POR MEDIÇÃO, não por gosto (13/08/2026): o rótulo mora na MESMA linha
#: do campo, e o campo é `hexpand` — sobram cerca de 36 caracteres. A primeira
#: redação ("...Cole o endereço da página do jogo na loja (store.steampowered.
#: com/app/…) ou digite o nome do jogo.") saiu da foto com reticências no meio,
#: e uma frase cortada é pior que uma frase curta. O que ela deve COLAR já está
#: dito duas vezes ao lado — no texto de dentro do campo e no tooltip dele.
MSG_NAO_RECONHECI = "Não reconheci este endereço."

#: O jogo existe, mas não está instalado aqui — o número vale assim mesmo, e
#: dizer isso é melhor que mostrar um número mudo. Mesmo teto de largura.
MSG_FORA_DA_MAQUINA = "Não instalado aqui (o número vale)."


def frase_do_campo_do_jogo(
    texto: str | None,
    nomes: Mapping[str, str],
    chaves: Mapping[str, str] | None = None,
) -> tuple[str, bool] | None:
    """O que fica ao lado do campo: ``(frase, é_alerta)``, ou ``None`` p/ esconder.

    Decisão PURA — `nomes` é o catálogo já lido do disco, para que o teste não
    precise nem de GTK nem da biblioteca dela.

    As quatro respostas, e por que cada uma:

    - campo vazio → ``None``. Alerta em campo em branco é ruído; quem cobra o
      preenchimento é o Salvar, com `MSG_STEAM_SEM_APPID`.
    - virou appid e o jogo está aqui → o NOME. ``851100`` sozinho não diz nada
      a ninguém, nem a ela daqui a um mês.
    - virou appid e o jogo não está aqui → `MSG_FORA_DA_MAQUINA`, sem alerta:
      é o caso normal do jogo que ela ainda vai comprar.
    - não virou appid → só reclama se PARECE endereço (`parece_endereco`).
      Enquanto ela digita o nome atrás da lista, silêncio.

    **A QUINTA, E ELA É DE 10/09/2026:** o campo pode agora guardar a
    `wm_class` de um jogo de lançador (``gotg.exe``), porque o `<datalist>`
    passou a oferecê-la. Sem `chaves`, esse texto caía no silêncio do último
    ramo — a lista ofereceria a linha e o rótulo ao lado não diria o nome do
    jogo que ela acabou de escolher. Com `chaves` (``{wm_class: nome}``), ele
    responde igual ao da Steam: **o NOME**.

    O silêncio continua sendo o certo para `chaves` vazio: sem catálogo de
    lançador não há o que afirmar, e afirmar "não reconheci" sobre um texto
    que é só o começo de um nome digitado é o alarme que a quarta resposta
    existe para evitar.
    """
    if not isinstance(texto, str) or not texto.strip():
        return None
    appid = steam_appid_de_texto(texto)
    if appid is not None:
        nome = nomes.get(str(appid))
        return (nome, False) if nome else (MSG_FORA_DA_MAQUINA, False)
    # A CONSULTA DOBRA A CAIXA dos dois lados — `nomes_das_janelas` entrega a
    # chave em minúsculas, e o que ela digita (ou o que o «Detectar» pegou da
    # janela) vem como o compositor o anunciou. Ver `jogo_da_janela`.
    do_lancador = (chaves or {}).get(texto.strip().casefold())
    if do_lancador:
        return (do_lancador, False)
    if parece_endereco(texto):
        return (MSG_NAO_RECONHECI, True)
    return None


__all__ = [
    "LANCADOR_DIRETO",
    "MSG_FORA_DA_MAQUINA",
    "MSG_NAO_RECONHECI",
    "PASTAS_DE_ATALHOS",
    "JogoLocal",
    "assinatura_da_biblioteca",
    "assinatura_das_janelas",
    "casa_com_o_que_ela_digitou",
    "catalogo_de_jogos",
    "chave_de_busca",
    "e_ferramenta_da_steam",
    "frase_do_campo_do_jogo",
    "jogo_da_janela",
    "jogos_com_janela",
    "jogos_da_biblioteca_steam",
    "jogos_de_janela",
    "jogos_diretos_dos_atalhos",
    "jogos_dos_atalhos_desktop",
    "jogos_dos_lancadores",
    "nomes_das_janelas",
    "nomes_por_appid",
    "ofertas_do_campo_do_jogo",
    "pastas_de_atalhos",
]
