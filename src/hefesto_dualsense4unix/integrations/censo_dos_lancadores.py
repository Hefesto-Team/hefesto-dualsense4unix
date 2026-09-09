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
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

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

    O INSTALADO SAI DO `*_install_info.json`, e não de um campo da biblioteca:
    o arquivo de biblioteca lista o que a CONTA tem, e é por isso que o disco
    dela dizia 37 com zero instalados — a leitura certa sobre um estado que
    parecia defeito.
    """
    cache = pasta / "store_cache"
    jogos: list[JogoDoLancador] = []
    erros: list[str] = []
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
            jogos.append(JogoDoLancador(
                chave=chave,
                nome=str(it.get(ch_nome) or it.get("title") or chave),
                loja=loja,
                instalado=chave in instalados))
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


def _lutris(pasta: Path) -> BibliotecaDoLancador:
    """Um `.yml` por jogo em `games/` — o nome do arquivo É o slug.

    NÃO SE IMPORTA UM PARSER DE YAML por isto: o que se precisa aqui é o SLUG,
    que é o nome do arquivo, e o `pyproject` não declara `pyyaml`. Uma
    dependência nova para ler um nome de arquivo seria o custo errado — e a
    §4 da sprint, que escreve `system: env:` no `.yml`, é quem vai precisar
    de um e vai declará-lo com a razão.
    """
    games = pasta / "games"
    if not games.is_dir():
        return BibliotecaDoLancador("Lutris", LIDO, pasta, [], [])
    jogos = [JogoDoLancador(chave=p.stem, nome=p.stem.replace("-", " "),
                            loja="Lutris", instalado=True, caminho=p)
             for p in sorted(games.glob("*.yml"))]
    return BibliotecaDoLancador("Lutris", LIDO, pasta, jogos, [])


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


def sabe_ler(lancador: str) -> bool:
    """Existe leitor de biblioteca para este lançador?

    É o que separa *"não sei ler"* de *"não há o que ler"* — e é a diferença
    entre o selo velho (`NÃO SEI`) e a frase nova. O cartão «Flatpak» cai
    aqui: ele não é lançador, é o runtime dos outros (§5.4 da sprint).
    """
    return lancador in _LEITORES
