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
diretório fora dos quatro do pedido dela. Máquina sem Steam, sem `.acf` ou sem
permissão devolve lista VAZIA em silêncio — o campo continua aceitando o appid
digitado, e degradar calado aqui é requisito, não descuido.
"""
from __future__ import annotations

import contextlib
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
#: `rungameid` quando isto foi medido).
PASTAS_DE_ATALHOS: tuple[str, ...] = (
    "~/.local/share/applications",
    "/usr/share/applications",
)

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
    #: ``"steam"`` (veio de um `appmanifest_*.acf`) ou ``"desktop"``.
    fonte: str

    @property
    def rotulo(self) -> str:
        """Como ele aparece na lista da completação: nome e número juntos.

        O número NÃO some do rótulo pelo mesmo motivo que ele não some de
        `steam_launch_options.rotulo_do_jogo`: é o que ela confere na Steam, e
        é o único identificador que os cadastros do projeto compartilham.
        """
        return f"{self.nome} (appid {self.appid})"


def e_ferramenta_da_steam(nome: str) -> bool:
    """O `.acf` é de infraestrutura (Proton, runtime, redistribuíveis)?"""
    return _FERRAMENTA_RE.match(nome.strip()) is not None


def chave_de_busca(texto: str) -> str:
    """Texto achatado para comparar: sem acento, sem caixa, sem espaço em volta.

    ``"Sackboy™: A Big Adventure"`` e ``"sackboy"`` têm de se encontrar, e
    ``"Pokémon"`` tem de casar com ``"pokemon"`` — ela digita no teclado dela,
    não no do catálogo.
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


def jogos_dos_atalhos_desktop(
    pastas: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """Os jogos dos `.desktop` que apontam para `steam://rungameid/<id>`.

    Lê `Exec=` e também `X-SteamAppId=`, que é o campo que o gerador dela
    escreve (medido em `meow-steam-851100.desktop`). `NoDisplay=true` é pulado:
    o atalho que o menu não mostra também não deve entrar na lista dela.
    """
    alvos = (
        list(pastas)
        if pastas is not None
        else [Path(p).expanduser() for p in PASTAS_DE_ATALHOS]
    )
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


def nomes_por_appid(jogos: Iterable[JogoLocal]) -> dict[str, str]:
    """``{"851100": "Touhou Luna Nights"}`` — o que a frase da tela consulta."""
    return {jogo.appid: jogo.nome for jogo in jogos}


def casa_com_o_que_ela_digitou(jogo: JogoLocal, digitado: str) -> bool:
    """A linha entra na lista suspensa para este texto?

    Casa por PEDAÇO do nome (``"sea"`` acha ``"Sea of Stars"``, e ``"stars"``
    também) e por começo do número — depois de escolher um jogo o campo fica
    com o appid, e o número é o que ela tem na frente para conferir.
    """
    chave = chave_de_busca(digitado)
    if not chave:
        return False
    return chave in chave_de_busca(jogo.nome) or jogo.appid.startswith(chave)


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
    """
    if not isinstance(texto, str) or not texto.strip():
        return None
    appid = steam_appid_de_texto(texto)
    if appid is not None:
        nome = nomes.get(str(appid))
        return (nome, False) if nome else (MSG_FORA_DA_MAQUINA, False)
    if parece_endereco(texto):
        return (MSG_NAO_RECONHECI, True)
    return None


__all__ = [
    "MSG_FORA_DA_MAQUINA",
    "MSG_NAO_RECONHECI",
    "PASTAS_DE_ATALHOS",
    "JogoLocal",
    "casa_com_o_que_ela_digitou",
    "catalogo_de_jogos",
    "chave_de_busca",
    "e_ferramenta_da_steam",
    "frase_do_campo_do_jogo",
    "jogos_da_biblioteca_steam",
    "jogos_dos_atalhos_desktop",
    "nomes_por_appid",
]
