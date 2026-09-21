"""O censo dos lançadores que NÃO são a Steam — LANCADORES-ZERO-01, 09/09/2026.

**A QUEIXA DELA, 08/09/2026, com o produto instalado e um print:**

    "a aba lançadores tá identificando nada."  # noqa-acento: citação dela

    "todos esses apps tão instalados agora no meu pc. pq não identificou? se é
     um problema com o ambiente flatpak construir o identificador é parte da
     solução a ser implementada."  # noqa-acento: citação dela

**O PRODUTO ACHAVA OS SEIS.** A busca por `.desktop` e por `PATH` funciona — o
cabeçalho dizia *"6 encontrados"*. O que faltava é o que o cartão da Steam faz
e os outros cinco não faziam: **ler a biblioteca**. Sem leitor, o selo caía em
`NÃO SEI`, e um selo grande e negativo sobre um lançador instalado lê-se como
*"não identificou"*.

O QUE ESTE MÓDULO É, e o que ele NÃO é
--------------------------------------

Ele é o **leitor de biblioteca** de cada lançador, com o mesmo contrato do
`prontuario_dos_jogos` da Steam: devolve jogos e **nunca diz "funciona"**. As
três respostas possíveis sobre um lançador são:

* ``NUNCA_ABERTO`` — a pasta de configuração não existe. **É uma resposta, e é
  melhor do que "não sei"**: o cartão diz *"abra o Lutris uma vez e eu leio a
  biblioteca"*. Não é dívida nossa — não há o que ler;
* ``LIDO`` — a biblioteca foi lida, com a contagem;
* ``ILEGIVEL`` — a pasta existe e o arquivo não pôde ser lido, com o motivo.

Ele **não** decide se os controles chegam ao jogo: isso é o veredito, e o
veredito da Steam mora no `prontuario_dos_jogos`. Aqui se responde *"o que
existe na biblioteca dele?"*, que é a pergunta que estava sem dono.

ONDE A BIBLIOTECA MORA, medido na máquina dela em 09/09/2026
-------------------------------------------------------------

Um flatpak guarda tudo em ``~/.var/app/<app-id>/``: ``config/`` faz as vezes de
``~/.config`` e ``data/`` de ``~/.local/share``. O nativo usa os dois de sempre.
**Este módulo procura nos DOIS**, e a ordem é flatpak-primeiro só porque é onde
os dela estão; achar o nativo primeiro daria o mesmo resultado.

    Heroic     config/heroic/store_cache/{legendary,gog,nile}_library.json
    Lutris     config/lutris/games/*.yml
    RetroArch  config/retroarch/playlists/*.lpl
    Dolphin    config/dolphin-emu/Dolphin.ini  (ISOPath0..N)
    mGBA       config/mgba/

**Medido no disco dela em 09/09:** só o Heroic tem pasta — 35 jogos da Epic e
2 da GOG na biblioteca, **0 instalados**, e `GamesConfig/` com dois arquivos de
log e nenhuma configuração de jogo. Os outros quatro nunca foram abertos.

**A EPIC FICA DENTRO DO HEROIC**, decisão dela de 08/09 (*"dentro heróic"*): ela
não é um cartão próprio, é uma das três lojas que o Heroic lê.

POR QUE UM MÓDULO, E NÃO UM LEITOR NA ABA
------------------------------------------

Porque o daemon vai precisar da mesma leitura para escrever o ambiente por jogo
(a §4 da sprint), e um leitor dentro do pacote da aba obrigaria a segunda
cópia. É a mesma disciplina do `prontuario_dos_jogos`, que a aba 07 e o
`sentinela_do_wrapper` dividem.
"""
from __future__ import annotations

import configparser
import contextlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from hefesto_dualsense4unix.integrations.identidade_de_janela import (
    umu_por_chave_do_heroic,
)

#: O QUE SE SABE SOBRE A BIBLIOTECA DE UM LANÇADOR. São três, e nenhuma é
#: "funciona" — a mesma disciplina do `prontuario_dos_jogos`.
NUNCA_ABERTO = "nunca_aberto"
LIDO = "lido"
ILEGIVEL = "ilegivel"

#: **E UM QUARTO, QUE NÃO É SOBRE A BIBLIOTECA:** o cartão «Flatpak» não tem
#: uma. Ele é o RUNTIME dos outros cinco, e a pergunta dele é outra — *"o vpad
#: entra no sandbox dos seus lançadores?"* (§5.4 da sprint).
#:
#: SEM ESTE ESTADO ele caía em `NUNCA_ABERTO` e o cartão dizia *"Abra Flatpak
#: uma vez e o Hefesto lê a biblioteca"* — uma frase falsa sobre um programa
#: que ela não abre e que não tem biblioteca nenhuma. Medido em 09/09/2026, na
#: primeira corrida deste módulo na máquina dela.
SEM_BIBLIOTECA = "sem_biblioteca"

#: A FRASE DO `NUNCA_ABERTO`, e ela NÃO confessa dívida nossa: não há o que
#: ler, e dizer isso é a resposta honesta. Ver a §3 da sprint.
FRASE_NUNCA_ABERTO = "Abra {nome} uma vez e o Hefesto lê a biblioteca."


@dataclass(frozen=True)
class JogoDoLancador:
    """Um jogo na biblioteca de um lançador que não é a Steam.

    `chave` é o identificador NATIVO daquele lançador — o `app_name` do
    Legendary, o `slug` do Lutris —, e não um número nosso: é por ela que o
    ambiente vai ser escrito (§4 da sprint), e inventar uma segunda
    identidade obrigaria a traduzir nos dois sentidos para sempre.
    """

    chave: str
    nome: str
    loja: str = ""
    instalado: bool = False
    caminho: Path | None = None
    #: O BINÁRIO QUE O JOGO ABRE, relativo à pasta de instalação —
    #: ``retail/gotg.exe``.
    #:
    #: **ELE NÃO É A CHAVE DE JANELA — 21/09/2026, medido.** Esta linha dizia
    #: *"É A CHAVE QUE FALTAVA"*, e a derivação caiu no dia em que ela abriu o
    #: jogo: ver `classe_de_janela`. O campo fica porque ele é verdade sobre o
    #: disco (é o binário, e a aba Lançadores o mostra); o que saiu é a
    #: promessa de que ele casa com a janela.
    executavel: str = ""
    #: O `umu-<N>` deste jogo, quando o lançador o conhece — **A CHAVE DE
    #: JANELA DE VERDADE**, 21/09/2026. Ver
    #: `integrations/identidade_de_janela.py` para a medição que a estabeleceu.
    umu_id: str = ""
    #: O appid da Steam, quando este jogo TAMBÉM existe lá. Segundo degrau.
    appid_da_steam: str = ""
    #: Conteúdo adicional (DLC, pacote de arte, redistribuível). **Não é jogo**
    #: — ver `e_acessorio`.
    dlc: bool = False

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

        **O ESTRAGO ESTAVA MEDIDO NO PERFIL DELA:**
        ``window_class: ["gotg.exe"]`` é uma regra que nunca casa — nenhum
        perfil ativava, nenhuma feature chegava ao jogo, e a queixa dela foi a
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
        """Isto é conteúdo adicional, e não um jogo?

        **O FILTRO É UM CAMPO DECLARADO, e não uma lista de nomes** — que é a
        diferença desta régua para a `jogos_locais.e_ferramenta_da_steam`, onde
        campo não existe e o filtro tem de ser por nome. Aqui a Epic e a GOG
        gravam ``install.is_dlc`` no próprio arquivo de biblioteca, e é ele que
        manda.

        MEDIDO NO DISCO DELA EM 10/09/2026, e o número da sprint estava velho:
        o enunciado dizia *"dos 37, um é `gog-redist` … São 36 jogos"*. São
        **oito** acessórios — sete DLC da Epic (trilha sonora, art book, roupa,
        wallpaper) mais o `gog-redist` (*Galaxy Common Redistributables*, que
        também traz `is_dlc: true`) —, e sobram **29 jogos**.
        """
        return self.dlc


@dataclass(frozen=True)
class BibliotecaDoLancador:
    """O que se sabe da biblioteca de UM lançador.

    `estado` é um dos três acima. `onde` é a pasta que foi lida (ou a que se
    procurou, quando `NUNCA_ABERTO`) — a tela a mostra, porque *"achei aqui"*
    sem o caminho não deixa ela conferir nada.
    """

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
        """A linha que o cartão imprime debaixo do selo.

        **UM SÓ LUGAR MONTA ESTA FRASE**, e é aqui: a aba 07 e qualquer relato
        de terminal a leem daqui. Duas montagens divergiriam no dia em que a
        contagem mudasse de forma — e "37 jogos" contra "37 na biblioteca" na
        mesma tela é exatamente a cara de um produto montado por duas pessoas.
        """
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


#: ONDE PROCURAR, por lançador: `(app-id do flatpak, subpasta de config)`.
#:
#: O `app-id` NÃO SE ADIVINHA do nome — `com.heroicgameslauncher.hgl` não
#: deriva de "Heroic" por regra nenhuma, e `net.retrodeck...` mudaria a conta.
#: Ele é dado, e a fonte é o `.desktop` que a aba já achou; esta tabela é a
#: queda para quando o chamador não o tem.
_ONDE: dict[str, tuple[str, str]] = {
    "Heroic": ("com.heroicgameslauncher.hgl", "heroic"),
    "Lutris": ("net.lutris.Lutris", "lutris"),
    "RetroArch": ("org.libretro.RetroArch", "retroarch"),
    "Dolphin": ("org.DolphinEmu.dolphin-emu", "dolphin-emu"),
    "mGBA": ("io.mgba.mGBA", "mgba"),
}


def _pasta_de_config(lancador: str, lar: Path) -> Path | None:
    """A pasta de configuração DESTE lançador, no flatpak ou no nativo.

    Devolve `None` quando nenhuma das duas existe — que é o `NUNCA_ABERTO`.

    OS DOIS CAMINHOS SÃO TENTADOS SEMPRE, e não escolhidos pelo `.desktop`:
    ela pode ter o flatpak instalado e a configuração vinda de uma instalação
    nativa anterior (ou o contrário). Ler os dois custa dois `is_dir()`.
    """
    app_id, sub = _ONDE.get(lancador, ("", ""))
    if not sub:
        return None
    for tentativa in (lar / ".var/app" / app_id / "config" / sub,
                      lar / ".config" / sub):
        if app_id and tentativa.is_dir():
            return tentativa
        if tentativa.is_dir():
            return tentativa
    return None


def _json(caminho: Path) -> object | None:
    """O JSON deste arquivo, ou `None` — e NUNCA levanta.

    O `cast` é para o `mypy`: `json.loads` devolve `Any`, e devolver `Any` de
    uma função que promete `object | None` apaga a checagem de quem a chama.
    """
    try:
        return cast("object", json.loads(caminho.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _heroic(pasta: Path) -> BibliotecaDoLancador:
    """As TRÊS lojas do Heroic — Epic (legendary), GOG e Amazon (nile).

    **A Epic fica aqui dentro**, decisão dela de 08/09/2026: *"dentro
    heróic"*. Ela não ganha cartão próprio.  # noqa-acento: citação dela

    O INSTALADO SAI DO `*_install_info.json`, e não SÓ de um campo da
    biblioteca: o arquivo de biblioteca lista o que a CONTA tem, e é por isso
    que o disco dela dizia 37 com zero instalados — a leitura certa sobre um
    estado que parecia defeito.

    **AS DUAS FONTES SE SOMAM DESDE 10/09/2026, e o motivo é medido.** Com um
    jogo baixado, o `legendary_library.json` passa a dizer ``is_installed:
    true`` e a trazer o `install.executable` — que é a CHAVE de janela (ver
    `JogoDoLancador.classe_de_janela`). Ler só o `install_info` continuaria
    certo sobre "está no disco?" e jogaria fora a chave; ler só a biblioteca
    perderia o caso dela de 09/09, em que o `install_info` era quem sabia.
    Então lê-se os dois, e o instalado é a UNIÃO.

    **E O QUE É ACESSÓRIO NÃO ENTRA**, pela mesma leitura: `install.is_dlc`.
    Ver `JogoDoLancador.e_acessorio` para os oito medidos no disco dela.
    """
    cache = pasta / "store_cache"
    jogos: list[JogoDoLancador] = []
    erros: list[str] = []
    # A CHAVE DE JANELA VEM DAQUI — 21/09/2026. Uma leitura só para a
    # biblioteca inteira: o `umu.json` é um dicionário de TODOS os jogos, e
    # reabri-lo por jogo pagaria 29 leituras de disco na pintura de uma aba.
    umu = umu_por_chave_do_heroic(cache)
    lojas = (("legendary", "Epic", "library", "app_name", "title"),
             ("gog", "GOG", "games", "app_name", "title"),
             ("nile", "Amazon", "library", "id", "product_title"))
    for arq, loja, campo, ch_id, ch_nome in lojas:
        dado = _json(cache / f"{arq}_library.json")
        if dado is None:
            continue
        itens = dado.get(campo) if isinstance(dado, dict) else None
        if not isinstance(itens, list):
            erros.append(f"{arq}_library.json não traz `{campo}` como lista")
            continue
        instalados = _instalados_do_heroic(cache / f"{arq}_install_info.json")
        for it in itens:
            if not isinstance(it, dict):
                continue
            chave = str(it.get(ch_id) or it.get("app_name") or it.get("id") or "")
            if not chave:
                continue
            instalacao = it.get("install")
            instalacao = instalacao if isinstance(instalacao, dict) else {}
            jogo = JogoDoLancador(
                chave=chave,
                nome=str(it.get(ch_nome) or it.get("title") or chave),
                loja=loja,
                instalado=chave in instalados or bool(it.get("is_installed")),
                caminho=(Path(str(instalacao["install_path"]))
                         if instalacao.get("install_path") else None),
                executavel=str(instalacao.get("executable") or ""),
                umu_id=umu.get(chave, ""),
                dlc=bool(instalacao.get("is_dlc")))
            if jogo.e_acessorio:
                continue
            jogos.append(jogo)
    return BibliotecaDoLancador("Heroic", LIDO, pasta, jogos, erros)


def _instalados_do_heroic(caminho: Path) -> set[str]:
    """As chaves que o `*_install_info.json` declara instaladas.

    QUEDA VAZIA E CALADA: sem o arquivo, ninguém está instalado — que é
    exatamente o estado dela em 09/09/2026. Um `erro` aqui poria uma frase de
    falha sobre um lançador que só não tem jogo baixado.
    """
    dado = _json(caminho)
    if isinstance(dado, dict):
        return {str(k) for k in dado}
    return set()


#: As colunas do `games` do `pga.db` que interessam, na ordem em que saem.
#: Nomeadas uma a uma, e nunca `SELECT *`: o Lutris acrescenta coluna entre
#: versões (medido: 23 colunas no dela), e ler por posição quebraria calado.
#: **`service`/`service_id` ENTRARAM EM 21/09/2026, e são o degrau 2.** As
#: colunas existem no `pga.db` dela (schema lido no disco, 23 colunas), e
#: quando `service == "steam"` o `service_id` É o appid da Steam daquele jogo.
#: Sem elas todo jogo do Lutris caía no «não sei», porque o degrau 1 (o umu-id)
#: só tem leitor no Heroic.
_COLUNAS_DO_LUTRIS = ("name", "slug", "executable", "directory", "installed",
                      "runner", "service", "service_id")

#: O valor da coluna `service` que significa "este jogo é da Steam". O Lutris
#: usa o mesmo vocabulário para `gog`, `egs`, `humble` — e para esses o
#: `service_id` é o id DAQUELA loja, que não vira `steam_app_<N>`. Casar por
#: igualdade, e não por "tem service_id", é o que impede um id da GOG de virar
#: uma chave de janela que nunca casa (o defeito R-12).
_SERVICO_DA_STEAM = "steam"


def _lutris(pasta: Path) -> BibliotecaDoLancador:
    """A biblioteca do Lutris — do `pga.db`, que é onde ela mora.

    **O LEITOR ANTIGO OLHAVA O ARQUIVO ERRADO, e o sintoma era a AUSÊNCIA de
    dado.** Ele lia `games/*.yml` e devolvia o `stem` como nome. Medido no
    disco dela em 11/09/2026:

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
    Nenhum degrau novo se inventa aqui: jogo do Lutris sem serviço da Steam
    continua respondendo «não sei» e mandando ao «Detectar», que é a resposta
    honesta até alguém abrir um e ler a classe.
    """
    jogos: list[JogoDoLancador] = []
    erros: list[str] = []
    vistos: set[str] = set()
    banco = pasta / "pga.db"
    if banco.is_file():
        try:
            conexao = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        except sqlite3.Error as erro:  # pragma: no cover - banco ilegível
            erros.append(f"pga.db não abriu: {erro}")
        else:
            with contextlib.closing(conexao):
                colunas = ", ".join(_COLUNAS_DO_LUTRIS)
                try:
                    linhas = list(
                        conexao.execute(f"SELECT {colunas} FROM games"))
                except sqlite3.Error as erro:
                    erros.append(f"pga.db não traz `games`: {erro}")
                    linhas = []
                for linha in linhas:
                    (nome, slug, executavel, pasta_do_jogo, instalado, _runner,
                     servico, id_do_servico) = linha
                    chave = str(slug or nome or "")
                    if not chave or chave in vistos:
                        continue
                    vistos.add(chave)
                    # O DEGRAU 2 SAI DAQUI. `identidade_de_janela` é quem o
                    # transforma em `steam_app_<N>`; este leitor só entrega o
                    # número, e só quando o serviço diz que ele é da Steam.
                    numero = str(id_do_servico or "").strip()
                    da_steam = (
                        numero
                        if str(servico or "").strip().casefold()
                        == _SERVICO_DA_STEAM and numero.isdigit()
                        else ""
                    )
                    jogos.append(JogoDoLancador(
                        chave=chave,
                        nome=str(nome or chave),
                        loja="Lutris",
                        instalado=bool(instalado),
                        caminho=(Path(str(pasta_do_jogo))
                                 if pasta_do_jogo else None),
                        executavel=str(executavel or ""),
                        appid_da_steam=da_steam))
    games = pasta / "games"
    if games.is_dir():
        for p in sorted(games.glob("*.yml")):
            if p.stem in vistos:
                continue
            vistos.add(p.stem)
            jogos.append(JogoDoLancador(
                chave=p.stem, nome=p.stem.replace("-", " "),
                loja="Lutris", instalado=True, caminho=p))
    jogos.sort(key=lambda j: (j.nome.casefold(), j.chave))
    return BibliotecaDoLancador("Lutris", LIDO, pasta, jogos, erros)


def _retroarch(pasta: Path) -> BibliotecaDoLancador:
    """As playlists `.lpl` — uma por console, com as ROMs dentro.

    O JOGO AQUI É A ROM, e a `chave` é o caminho dela: o RetroArch é UM
    processo para todos, então não há identificador por jogo do lado do
    lançador. É por isso que a cura dele é `flatpak override` no emulador
    inteiro, e não por jogo (§4 da sprint).
    """
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
    """As PASTAS de ISO do `Dolphin.ini` (`ISOPath0..N`) — não os jogos.

    O Dolphin guarda o cache da biblioteca num binário próprio; o que se lê
    em texto são as pastas onde ele procura. **Contar pastas e chamá-las de
    jogos seria mentir** — então o que sai daqui são as pastas, com
    `instalado=False`, e o resumo dirá "0 instalados" com honestidade.
    """
    ini = pasta / "Dolphin.ini"
    if not ini.is_file():
        return BibliotecaDoLancador("Dolphin", LIDO, pasta, [], [])
    cfg = configparser.ConfigParser(strict=False)
    try:
        cfg.read_string(ini.read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error) as erro:
        return BibliotecaDoLancador("Dolphin", ILEGIVEL, pasta, [], [str(erro)])
    #: `isopath0`, `isopath1`… E NUNCA `isopaths`, que é a CONTAGEM. Sem o
    #: dígito, o `ISOPaths = 2` entrava na lista como se fosse uma pasta
    #: chamada "2" — medido na primeira corrida da régua, 09/09/2026.
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


_LEITORES = {"Heroic": _heroic, "Lutris": _lutris, "RetroArch": _retroarch,
             "Dolphin": _dolphin, "mGBA": _mgba}


def biblioteca_de(lancador: str, lar: Path | None = None) -> BibliotecaDoLancador:
    """O que este lançador tem na biblioteca — ou por que não se sabe.

    **NUNCA LEVANTA.** A aba pinta a cada tique; uma exceção aqui apagaria a
    coluna inteira por um `.json` truncado. O que não se pôde ler vira
    `ILEGIVEL` com o motivo, que a tela mostra.

    :param lar: o `HOME` a inspecionar. O padrão é o de verdade; a régua passa
        um lar de mentira — é o que permite medir os cinco leitores sem ter os
        cinco lançadores instalados.
    """
    lar = Path.home() if lar is None else lar
    leitor = _LEITORES.get(lancador)
    if leitor is None:
        #: NÃO É `NUNCA_ABERTO`: quem não tem leitor pode simplesmente não ter
        #: biblioteca — é o caso do «Flatpak», que é o runtime dos outros. Ver
        #: `SEM_BIBLIOTECA`.
        return BibliotecaDoLancador(lancador, SEM_BIBLIOTECA, None, [], [])
    pasta = _pasta_de_config(lancador, lar)
    if pasta is None:
        return BibliotecaDoLancador(lancador, NUNCA_ABERTO, None, [], [])
    try:
        return leitor(pasta)
    except OSError as erro:
        return BibliotecaDoLancador(lancador, ILEGIVEL, pasta, [], [str(erro)])


#: **A CHAVE DO CARTÃO NÃO É O NOME DO LANÇADOR**, e ignorar isso deu cartão
#: mudo na primeira ligação: o desenho chama o cartão de `heroic` e o exibe
#: como *"Heroic (Epic · GOG)"*; o `emuladores` é UM cartão com DOIS programas
#: dentro (*"Dolphin · mGBA"*), por decisão de desenho. Casar por nome achava
#: só `Lutris` e `RetroArch`.
#:
#: Um cartão pode ter mais de um lançador, então o valor é uma TUPLA.
_DO_CARTAO: dict[str, tuple[str, ...]] = {
    "heroic": ("Heroic",),
    "lutris": ("Lutris",),
    "retroarch": ("RetroArch",),
    "emuladores": ("Dolphin", "mGBA"),
    #: O «Flatpak» é o RUNTIME dos outros — não tem biblioteca (§5.4).
    "flatpak": (),
}


def biblioteca_do_cartao(chave: str, lar: Path | None = None
                         ) -> BibliotecaDoLancador:
    """A biblioteca que UM CARTÃO da aba 07 representa.

    UM CARTÃO PODE SER DOIS PROGRAMAS (`emuladores` = Dolphin + mGBA), e o
    resumo tem de somá-los: dizer "Dolphin: 2" num cartão que se chama
    *"Dolphin · mGBA"* deixaria o mGBA sem resposta na tela.

    A SOMA SÓ ACONTECE ENTRE OS QUE FORAM LIDOS. Se um nunca foi aberto e o
    outro tem biblioteca, o estado é `LIDO` — há o que mostrar; se NENHUM foi
    aberto, é `NUNCA_ABERTO`, e a frase manda abrir. Somar um `NUNCA_ABERTO`
    como zero jogos diria "biblioteca vazia" sobre um programa que ela nunca
    rodou, que é justamente a distinção que este módulo existe para manter.
    """
    nomes = _DO_CARTAO.get(chave)
    if nomes is None:
        return BibliotecaDoLancador(chave, SEM_BIBLIOTECA, None, [], [])
    if not nomes:
        return BibliotecaDoLancador(chave, SEM_BIBLIOTECA, None, [], [])
    partes = [biblioteca_de(n, lar) for n in nomes]
    lidas = [b for b in partes if b.estado == LIDO]
    if not lidas:
        #: O PRIMEIRO MANDA quando nenhum foi lido — e a frase dele nomeia um
        #: programa de verdade, que é o que ela precisa abrir.
        return partes[0]
    return BibliotecaDoLancador(
        lancador=" · ".join(nomes),
        estado=LIDO,
        onde=lidas[0].onde,
        jogos=[j for b in lidas for j in b.jogos],
        erros=[e for b in partes for e in b.erros])


def jogos_com_chave_de_janela(
    lar: Path | None = None,
) -> list[tuple[str, JogoDoLancador]]:
    """``[(lançador, jogo)]`` — só os jogos que dá para RECONHECER numa janela.

    **É A METADE HONESTA DA §3 DA SPRINT**, e a linha que ela corta é de
    propósito. O enunciado propunha levar os 36 do Heroic ao campo «Nome do
    Jogo» *"sem custar um pixel"*; medido em 10/09/2026, oferecer um jogo sem
    chave é oferecer uma linha que **nunca casa com janela nenhuma** — o
    defeito R-12, que esta casa já pagou uma vez. Então a oferta é do que tem
    endereço, e o resto fica de fora até ter.

    Quem tem chave hoje, no disco dela: **1** — *Marvel's Guardians of the
    Galaxy*, `gotg.exe`. Os outros 28 do Heroic não estão baixados; as 7 ROMs
    do RetroArch e a pasta do Dolphin não têm janela própria (um processo para
    todas); o Lutris está aberto e vazio.

    NUNCA LEVANTA — `biblioteca_de` já promete isso, e esta função é chamada de
    dentro da pintura da aba Perfis.

    :param lar: o `HOME` a inspecionar. Uma régua passa um lar de mentira.
    """
    achados: list[tuple[str, JogoDoLancador]] = []
    for nome in _LEITORES:
        for jogo in biblioteca_de(nome, lar).jogos:
            if jogo.instalado and jogo.classe_de_janela:
                achados.append((nome, jogo))
    return achados


#: O QUE CADA LEITOR ABRE DE VERDADE — relativo à pasta de configuração. É
#: ESTA tabela que `assinatura_das_bibliotecas` assina, e não a pasta de cima.
#:
#: **A CÓPIA DO MOLDE PERDEU A PROPRIEDADE QUE O FAZ FUNCIONAR — medido em
#: 11/09/2026.** `jogos_locais.assinatura_da_biblioteca` assina a `steamapps`,
#: e funciona porque a `steamapps` é a pasta que SEGURA os manifestos:
#: instalar ou desinstalar um jogo CRIA ou APAGA um arquivo dentro dela, e o
#: `mtime` de um diretório muda quando isso acontece. A biblioteca do Heroic
#: não é uma pasta de manifestos — é UM arquivo,
#: `store_cache/legendary_library.json`, reescrito no lugar. E **o `mtime` de
#: um diretório não muda quando um arquivo de um SUBdiretório é reescrito**:
#: assinar `…/config/heroic` dava a mesma impressão com um jogo novo
#: instalado, o caderno de `jogos_locais.nomes_das_janelas` nunca invalidava,
#: e a aba Perfis — que é PINTURA num processo longo — CONGELAVA a resposta
#: até ela reiniciar o produto. O gatilho é exatamente o passo que a sprint
#: manda ela dar: *instalar um jogo do Heroic*.
#:
#: Um padrão com `*` assina a PASTA (nasceu ou morreu arquivo) **e** cada
#: arquivo que casa (o conteúdo mudou). Sem `*`, assina o arquivo.
_FONTES: dict[str, tuple[str, ...]] = {
    #: O `umu.json` ENTROU EM 21/09/2026 — é ele que traz a CHAVE DE JANELA
    #: desde a LANCADOR-AGNOSTICO-01. Sem ele na assinatura, instalar um jogo
    #: novo do Heroic não invalidaria o caderno pela chave, e a aba Perfis
    #: (que é PINTURA num processo longo) congelaria a resposta até ela
    #: reiniciar o produto — o mesmo defeito que a nota acima descreve.
    "Heroic": ("store_cache/*_library.json", "store_cache/*_install_info.json",
               "store_cache/umu.json"),
    #: O `-wal` ENTRA, e é requisito e não zelo: em modo WAL o sqlite escreve
    #: as linhas novas no `pga.db-wal` e pode não tocar no `pga.db`. Quem lê
    #: em `mode=ro` enxerga os dois; a impressão tem de enxergar os dois.
    "Lutris": ("pga.db", "pga.db-wal", "games/*.yml"),
    "RetroArch": ("playlists/*.lpl",),
    "Dolphin": ("Dolphin.ini",),
    "mGBA": ("config.ini",),
}


def _impressao(caminho: Path) -> tuple[str, int, int]:
    """``(caminho, mtime_ns, tamanho)`` de um arquivo ou pasta — e nunca levanta.

    O TAMANHO ENTRA JUNTO porque o `mtime` sozinho tem a resolução do sistema
    de arquivos, e duas escritas dentro do mesmo tique existem — um
    `legendary_library.json` que ganha um jogo muda de tamanho sempre.

    Ausente entra com ``-1`` em vez de sumir da lista: instalar o Lutris (ou
    baixar o primeiro jogo, que é quando o `*_install_info.json` nasce)
    também tem de contar como mudança.
    """
    try:
        st = os.stat(caminho)
    except OSError:
        return (str(caminho), -1, -1)
    return (str(caminho), st.st_mtime_ns, st.st_size)


def assinatura_das_bibliotecas(
    lar: Path | None = None,
) -> tuple[tuple[str, int, int], ...]:
    """Impressão BARATA das cinco bibliotecas — **do que se LÊ**, não da pasta.

    Irmã de `jogos_locais.assinatura_da_biblioteca`, e **separada dela de
    propósito**: aquela responde *"a biblioteca da STEAM mudou?"* olhando as
    `steamapps`, e um `mtime` de `~/.var/app/…/heroic` não diz nada sobre a
    Steam. As duas continuam sendo duas funções, cada uma com o seu dono.

    **QUEM PRECISA DAS DUAS AS LÊ EM PAR, e isso mudou em 11/09/2026**
    (PERFIL-DOS-LANCADORES-E1): `profiles.loader._talvez_semear_jogos` compara
    `(assinatura_da_biblioteca(), assinatura_das_bibliotecas())` porque agora
    ele semeia perfil para as DUAS origens, e um jogo baixado pelo Heroic tem
    de acordar a varredura. O preço está medido e aceito no comentário daquele
    ponto: os 33 `.acf` da Steam são relidos uma vez quando o Heroic reescreve
    a biblioteca, no máximo uma vez por `INTERVALO_MINIMO_DA_VARREDURA_S`.

    **O QUE ELA ASSINA ESTÁ EM `_FONTES`, e o porquê está lá também**: assinar
    a pasta de cima é o defeito que esta função teve até 11/09/2026 — ela
    nunca invalidava para o Heroic, que é justamente o lançador da queixa
    dela. A pasta de configuração continua entrando: instalar o lançador
    depois também é mudança.
    """
    linhas: list[tuple[str, int, int]] = []
    lar = Path.home() if lar is None else lar
    for nome in _LEITORES:
        pasta = _pasta_de_config(nome, lar)
        if pasta is None:
            linhas.append((nome, -1, -1))
            continue
        linhas.append(_impressao(pasta))
        for padrao in _FONTES.get(nome, ()):
            if "*" not in padrao:
                linhas.append(_impressao(pasta / padrao))
                continue
            sub, _, molde = padrao.rpartition("/")
            onde = pasta / sub if sub else pasta
            linhas.append(_impressao(onde))
            try:
                achados = sorted(onde.glob(molde))
            except OSError:  # pragma: no cover - pasta ilegível
                achados = []
            linhas.extend(_impressao(a) for a in achados)
    return tuple(linhas)


def sabe_ler(lancador: str) -> bool:
    """Existe leitor de biblioteca para este lançador?

    É o que separa *"não sei ler"* de *"não há o que ler"* — e é a diferença
    entre o selo velho (`NÃO SEI`) e a frase nova. O cartão «Flatpak» cai
    aqui: ele não é lançador, é o runtime dos outros (§5.4 da sprint).
    """
    return lancador in _LEITORES
