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
``~/.config`` e ``data/`` de ``~/.local/share``, e dentro da caixa o XDG é sempre
esse. O nativo segue o XDG como o lançador segue: ``$XDG_CONFIG_HOME`` e
``$XDG_DATA_HOME``, e sem eles ``~/.config`` e ``~/.local/share`` (:class:`_Onde`).
**Este módulo procura nos DOIS**, e com as duas casas no disco vale a do
programa instalado (:func:`_pastas_lidas`): a outra pode ser sobra.

    Heroic     config/heroic/store_cache/{legendary,gog,nile}_library.json
               e o registro dos instalados de cada loja (_REGISTROS_DO_HEROIC)
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
    #: O ARQUIVO DE CONFIGURAÇÃO DESTE JOGO NO LANÇADOR, quando ele tem um: o
    #: `games/<configpath>.yml` do Lutris (A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01,
    #: 02/10/2026). É a camada que só este jogo lê, e é nela que a exclusão
    #: escreve (`cura_por_estrada`, «A CAMADA DO JOGO DO LUTRIS»).
    configuracao: Path | None = None
    #: O JOGO ABRE PELO SCRIPT DO PROTON (02/10/2026,
    #: O-JOGO-EXCLUIDO-DO-LUTRIS-VOLTA-AO-XALIA-DO-PROTON-01): no Lutris, o
    #: runner `wine` com a versão padrão ou com um Proton (`_UmuDoLutris`, a
    #: mesma conta do umu-id). O padrão do xalia é do script do Proton, e o Wine
    #: sem ele não sobe o xalia: a camada do jogo excluído depende disto.
    pelo_proton: bool = False

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
        gravam ``install.is_dlc`` no próprio arquivo de biblioteca, e o
        registro dos instalados também: o jogo instalado depois da última
        releitura não tem ``install`` na biblioteca, e o campo vem do registro
        (:func:`_heroic`).

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

    `estado` é um dos três acima. `onde` é a pasta que foi lida (a primeira,
    quando os dois programas estão instalados e as duas casas se somam) — a
    tela a mostra, porque *"achei aqui"* sem o caminho não deixa ela conferir
    nada.
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


#: OS LANÇADORES CUJA CONFIGURAÇÃO CAI NOS DADOS quando a pasta `config/` não
#: existe. O Lutris 0.5.22 (`lutris/settings.py:21-27`, lido no Flatpak dela em
#: 02/10/2026): `CONFIG_DIR` é `<config>/lutris` se essa pasta existir, e senão
#: é o `DATA_DIR`, `<dados>/lutris` (*«we're deprecating ~/.config/lutris»*); e
#: ele não cria a `config/`. Quem instala o Lutris hoje tem só a de dados.
_CONFIG_CAI_NOS_DADOS = frozenset({"Lutris"})


@dataclass(frozen=True)
class _Onde:
    """Onde o censo procura: o lar, as duas pastas do XDG dele e a raiz do Flatpak.

    **O XDG ANDA JUNTO COM O LAR (02/10/2026,
    O-CENSO-RESPONDE-COMO-O-LANCADOR-RESPONDE-01).** O Lutris nativo guarda a
    casa em `GLib.get_user_config_dir()` e `get_user_data_dir()`
    (`settings.py:21-22` do 0.5.22), e o Heroic nativo no `appData` do Electron:
    os dois seguem o `XDG_CONFIG_HOME` e o `XDG_DATA_HOME`. Medido num lar de
    mentira com os dois XDG fora do padrão: o censo de casa fixa dizia «Abra
    Lutris uma vez…» e «Abra Heroic uma vez…» com os dois cheios.

    O lar de verdade (``lar=None``) lê o XDG do ambiente; quem passa um lar de
    mentira passa o XDG dele, ou fica com o `<lar>/.config` e o
    `<lar>/.local/share`. Ler o ambiente com um lar explícito faria a régua de
    lar de mentira ler a casa de outro lugar (a suíte isola o XDG num
    `tmp_path/.xdg/`) e passar vazia. Valor relativo não vale, como na spec do
    XDG e no `uninstall.sh`.
    """

    lar: Path
    config: Path
    dados: Path
    #: A instalação do Flatpak do SISTEMA (``None`` = `/var/lib/flatpak`), que
    #: o `sandbox_dos_lancadores` lê ao lado da do usuário.
    raiz_sistema: Path | None = None


def _do_ambiente(variavel: str) -> Path | None:
    """A pasta desta variável do XDG, quando o ambiente a dá absoluta."""
    valor = os.environ.get(variavel, "").strip()
    return Path(valor) if os.path.isabs(valor) else None


def _onde(lar: Path | None = None, xdg_config: Path | None = None,
          xdg_data: Path | None = None, raiz_sistema: Path | None = None) -> _Onde:
    """O :class:`_Onde` de quem chama: o lar de verdade com o XDG do ambiente,
    ou o lar dado com o XDG dado (e sem ele, o padrão dentro do lar)."""
    if lar is None:
        lar = Path.home()
        xdg_config = xdg_config or _do_ambiente("XDG_CONFIG_HOME")
        xdg_data = xdg_data or _do_ambiente("XDG_DATA_HOME")
    return _Onde(lar, xdg_config or lar / ".config", xdg_data or lar / ".local/share",
                 raiz_sistema)


def _casas(lancador: str, onde: _Onde) -> tuple[tuple[Path, Path], ...]:
    """``((config, dados), ...)`` deste lançador: o Flatpak primeiro, o nativo depois.

    A do Flatpak não segue o XDG de fora: dentro da caixa ele é sempre
    `~/.var/app/<id>/{config,data}`.
    """
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
    """As pastas de configuração que o censo lê, pela regra das duas casas.

    Em cada casa vale a regra do lançador (:func:`_pasta_da_casa`): no Lutris, a
    `config/` e, sem ela, a de dados. Vazio é o `NUNCA_ABERTO`.

    **COM AS DUAS CASAS NO DISCO, VALE A DO PROGRAMA INSTALADO (02/10/2026, por
    delegação, a validar por ela).** A primeira pasta que existia ganhava, o
    Flatpak antes do nativo. Medido num lar de mentira: o Lutris nativo com dois
    jogos e a pasta do Flatpak com o banco vazio (o Flatpak aberto uma vez, ou a
    sobra de um `flatpak uninstall` sem `--delete-data`), e o cartão dizia «A
    biblioteca está vazia.»; os dois jogos sumiam do cartão, da lista de
    exclusão e da chave de janela. Cada lançador responde pela casa dele, e o que
    ela abre é um programa instalado, não uma pasta (:func:`_instalacoes`). Com
    os dois instalados, as duas casas se somam, como o «Dolphin · mGBA»; com
    nenhum, a regra de antes (o Flatpak primeiro). Com uma casa só não há o que
    escolher, e o disco não é olhado.
    """
    achadas = [(i, pasta) for i, (config, dados) in enumerate(_casas(lancador, onde))
               if (pasta := _pasta_da_casa(lancador, config, dados)) is not None]
    if len(achadas) < 2:
        return tuple(pasta for _, pasta in achadas)
    instalados = _instalacoes(lancador, onde)
    escolhidas = tuple(pasta for i, pasta in achadas if instalados[i])
    return escolhidas or (achadas[0][1],)


def _instalacoes(lancador: str, onde: _Onde) -> tuple[bool, bool]:
    """``(o Flatpak está instalado, o nativo está instalado)`` — e nunca levanta.

    O Flatpak, pelo dono que já responde isso
    (`sandbox_dos_lancadores.app_ids_instalados`: a instalação do usuário e a do
    sistema). O nativo, pelas agulhas com que a aba Lançadores acha o programa
    (:func:`_instalado_no_nativo`).
    """
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
    """``(atalhos, comandos)`` do programa nativo deste lançador.

    As agulhas são as que o cartão já usa para achar o lançador
    (`desenho_dos_lancadores.SEM_FONTE`, módulo de dados puro, só lido): um
    segundo lugar com os nomes envelheceria calado. No cartão de dois programas
    («Dolphin · mGBA»), as de cada um são o `app-id` dele e os nomes que começam
    pela subpasta dele (`dolphin-emu`, `mgba-qt`, `mgba`).
    """
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

    cartao = next((c for c, nomes in _DO_CARTAO.items() if lancador in nomes), "")
    item = next((s for s in desenho.SEM_FONTE if s.chave == cartao), None)
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
    """A primeira pasta que o censo lê deste lançador (:func:`_pastas_lidas`);
    `None` é o `NUNCA_ABERTO`."""
    pastas = _pastas_lidas(lancador, _onde(lar))
    return pastas[0] if pastas else None


def pastas_lidas(lancador: str, lar: Path | None = None, *,
                 xdg_config: Path | None = None, xdg_data: Path | None = None,
                 raiz_sistema: Path | None = None) -> tuple[Path, ...]:
    """As pastas de configuração que o censo lê deste lançador — a regra das
    duas casas (:func:`_pastas_lidas`). Quem escreve na casa do lançador (a
    carona do Heroic) escreve nestas, e em nenhuma outra."""
    return _pastas_lidas(lancador, _onde(lar, xdg_config, xdg_data, raiz_sistema))


def pastas_que_existem(lancador: str, lar: Path | None = None, *,
                       xdg_config: Path | None = None,
                       xdg_data: Path | None = None) -> tuple[Path, ...]:
    """Toda pasta de configuração deste lançador que existe, instalado ou não.

    É a rede do desfazer: o `uninstall.sh` tira o que é nosso de toda casa,
    porque desinstalar o lançador não leva a casa dele.
    """
    return tuple(pasta for config, dados in _casas(lancador, _onde(lar, xdg_config, xdg_data))
                 if (pasta := _pasta_da_casa(lancador, config, dados)) is not None)


def pasta_do_flatpak(lancador: str, lar: Path | None = None) -> Path | None:
    """A pasta de configuração da casa FLATPAK deste lançador, pela mesma regra.

    A camada do jogo excluído do Lutris só existe no Flatpak (o nativo não
    ganha camada), e a casa dele é a que este censo lê: uma regra, um dono.
    """
    casas = _casas(lancador, _onde(lar))
    return _pasta_da_casa(lancador, *casas[0]) if casas else None


def _json(caminho: Path) -> object | None:
    """O JSON deste arquivo, ou `None` — e NUNCA levanta.

    O `cast` é para o `mypy`: `json.loads` devolve `Any`, e devolver `Any` de
    uma função que promete `object | None` apaga a checagem de quem a chama.
    """
    try:
        return cast("object", json.loads(caminho.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


#: O REGISTRO DOS INSTALADOS DE CADA LOJA, relativo à casa do Heroic — o arquivo
#: que o próprio Heroic lê para responder «instalado» (o `refreshInstalled` de
#: cada loja, lido no `app.asar` do 2.22.3 dela em 02/10/2026, `main.js`):
#:
#: * Epic: as chaves do `legendary/installed.json` (`:40153-40176`), mais os
#:   pares ``[app_name, plataforma]`` do `third-party-installed.json`, que só
#:   existe com jogo de loja de terceiro (`:39169-39187`);
#: * GOG: o `appName` de cada item de ``installed`` (`:38515-38524`);
#: * Amazon: o `id` de cada item da lista (`:41557-41575`).
#:
#: O primeiro de cada loja é o que tem de existir; o segundo da Epic, não.
_REGISTROS_DO_HEROIC: dict[str, tuple[str, ...]] = {
    "legendary": ("legendaryConfig/legendary/installed.json",
                  "legendaryConfig/legendary/third-party-installed.json"),
    "gog": ("gog_store/installed.json",),
    "nile": ("nile_config/nile/installed.json",),
}


def _itens_do_registro(arq: str, rel: str, dado: object) -> dict[str, dict[str, object]] | None:
    """``{chave: o que o registro diz do jogo}`` na forma que o Heroic grava;
    ``None`` = o arquivo não tem a forma (o registro torto)."""
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
    """``(os instalados desta loja, o registro dela existe, erros)``.

    O registro ausente é «nenhum instalado nesta loja», como o Heroic responde.
    O torto (não abre, ou não tem a forma) é erro: quem o lê como vazio tiraria
    morador do prefixo por um arquivo que ninguém entendeu.
    """
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
    """As TRÊS lojas do Heroic — Epic (legendary), GOG e Amazon (nile).

    **A Epic fica aqui dentro**, decisão dela de 08/09/2026: *"dentro
    heróic"*. Ela não ganha cartão próprio.  # noqa-acento: citação dela

    OS JOGOS SAEM DA BIBLIOTECA (`store_cache/*_library.json`), que lista o
    que a CONTA tem; é por isso que o disco dela dizia 37 com zero instalados.

    **O INSTALADO SAI DO REGISTRO DE CADA LOJA (02/10/2026,
    O-CENSO-RESPONDE-COMO-O-LANCADOR-RESPONDE-01)**, o mesmo que o Heroic lê
    (:data:`_REGISTROS_DO_HEROIC`). Os dois arquivos que respondiam antes não
    são isso: a biblioteca é cache da conta (o `refresh()` da GOG grava todo
    jogo com `is_installed: false`, e na Epic a marca é a do momento da
    releitura), e o `*_install_info.json` é o cache do diálogo de instalar (todo
    jogo cujo diálogo ela abriu, instalado ou não; o «Limpar cache» o esvazia).
    Medido num lar de mentira: com A excluído e E e G instalados no mesmo
    prefixo, o censo dizia E e G fora, e a lista de exclusão tirava o device KS
    do prefixo sem ela ter excluído nenhum dos dois.

    **O REGISTRO QUE NÃO RESPONDE VIRA ERRO** (por delegação, a validar por
    ela): o torto, e o ausente com a biblioteca dizendo `is_installed: true`
    naquela loja (o Heroic grava `{}` ou `[]` quando o último jogo sai, e não
    apaga o arquivo; a ausência com um instalado é outra forma de disco). O
    censo com erro não tira ninguém do prefixo (`lista_de_exclusao`), e naquela
    loja o instalado fica o da biblioteca, o melhor que se tem.

    O `install_path`, o `executable` e o `is_dlc` vêm da biblioteca e, quando
    ela não os tem, do registro (o jogo instalado depois da releitura não tem
    `install` na biblioteca, e sem o `is_dlc` do registro a DLC dele contaria
    como jogo). **E O QUE É ACESSÓRIO NÃO ENTRA** (`JogoDoLancador.e_acessorio`).
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
        # A LOJA SEM CONTA NÃO É BIBLIOTECA TORTA (02/10/2026): o Heroic grava
        # `{}` na biblioteca da loja em que ninguém entrou (o `nile_library.json`
        # dela, lido só para leitura). Torta é a chave que vem e não é lista.
        if isinstance(dado, dict) and campo not in dado:
            continue
        itens = dado.get(campo) if isinstance(dado, dict) else None
        if not isinstance(itens, list):
            erros.append(f"{arq}_library.json não traz `{campo}` como lista")
            continue
        itens = [it for it in itens if isinstance(it, dict)]
        registro, existe, erros_da_loja = _registro_do_heroic(pasta, arq)
        #: O ACESSÓRIO NÃO É CONTRADIÇÃO: o «Galaxy Common Redistributables»
        #: chega à biblioteca com `is_installed: true` e `install.is_dlc: true`
        #: sem estar no registro (no disco dela, o único `true` da GOG), e a
        #: conta ligada sem jogo baixado não tem registro. Ele não entra no
        #: censo, e não pode calá-lo.
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


#: As colunas do `games` do `pga.db` que interessam, na ordem em que saem.
#: Nomeadas uma a uma, e nunca `SELECT *`: o Lutris acrescenta coluna entre
#: versões (medido: 23 colunas no dela), e ler por posição quebraria calado.
#: **`service`/`service_id` ENTRARAM EM 21/09/2026, e são o degrau 2.** As
#: colunas existem no `pga.db` dela (schema lido no disco, 23 colunas), e
#: quando `service == "steam"` o `service_id` É o appid da Steam daquele jogo.
#: Sem elas todo jogo do Lutris caía no «não sei».
#:
#: **02/10/2026 (A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01): o degrau 1 (o umu-id)
#: passou a ter leitor no Lutris também** — ver `_UmuDoLutris`. A frase que
#: ficava aqui dizia que ele «só tem leitor no Heroic».
#:
#: O `configpath` é o nome do `games/<configpath>.yml` do jogo (`lutris/game.py`,
#: `game_config_id`), e só a exclusão o usa.
_COLUNAS_DO_LUTRIS = ("name", "slug", "executable", "directory", "installed",
                      "runner", "service", "service_id", "configpath")

#: AS ÚNICAS COLUNAS EXIGIDAS: sem o `name` e o `slug` não há jogo. As outras que
#: faltarem entram como `NULL` (02/10/2026,
#: O-CENSO-RESPONDE-COMO-O-LANCADOR-RESPONDE-01). Medido num lar de mentira com
#: um banco sem `service`, `service_id` e `discord_id`: o `SELECT` caía com «no
#: such column: service», e o cartão dizia «A biblioteca está vazia.» com dois
#: jogos no banco. O Lutris 0.5.22 acrescenta as colunas que faltam ao abrir
#: (`database/schema.py:113-144`, `migrate`); o caso é o banco que nenhum Lutris
#: novo abriu, e o censo, que abre em `mode=ro`, não migra o banco de ninguém.
_COLUNAS_EXIGIDAS_DO_LUTRIS = ("name", "slug")

#: O RUNNER QUE PASSA PELO UMU. No Lutris 0.5.22 (lido no fonte instalado nela,
#: `runners/wine.py:1275-1281`), só o runner `wine` pede o `GAMEID` ao
#: `util/wine/proton.get_game_id`, e só quando a versão do Wine é um Proton ou
#: o próprio umu. Um jogo nativo (`linux`) ou de emulador nunca vira
#: `steam_app_<N>`.
_RUNNER_DO_UMU = "wine"

#: A versão do Wine que o Lutris trata como «nenhuma escolhida» e entrega ao umu
#: (`util/wine/wine.GE_PROTON_LATEST`; `get_default_wine_version` a devolve).
_VERSAO_PADRAO_DO_LUTRIS = "ge-proton"

#: O valor da coluna `service` que significa "este jogo é da Steam". O Lutris
#: usa o mesmo vocabulário para `gog`, `egs`, `humble` — e para esses o
#: `service_id` é o id DAQUELA loja, que não vira `steam_app_<N>`. Casar por
#: igualdade, e não por "tem service_id", é o que impede um id da GOG de virar
#: uma chave de janela que nunca casa (o defeito R-12).
_SERVICO_DA_STEAM = "steam"


def _lutris(pasta: Path, lar: Path | None = None, *,
            onde: _Onde | None = None) -> BibliotecaDoLancador:
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
                    # transforma em `steam_app_<N>`; este leitor só entrega o
                    # número, e só quando o serviço diz que ele é da Steam.
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
    """Um `.yml` do Lutris como dicionário; ausente, torto ou sem PyYAML = ``None``.

    O IMPORT É TARDIO, e é estrutural: o desfazer do uninstall importa este
    módulo com o `python3` do sistema, que pode não ter o PyYAML. O leitor é o
    mesmo do Lutris (`util/yaml.read_yaml_from_file`: `yaml.safe_load`).
    """
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
    """O `GAMEID` que o Lutris daria a cada jogo — a regra dele, lida no fonte.

    No Lutris 0.5.22 (`runners/wine.py:1275-1281` e
    `util/wine/proton.py:196-221`, lidos no Flatpak instalado nela em
    02/10/2026), um jogo do runner `wine` passa pelo umu quando a versão do Wine
    é a padrão (`ge-proton`, que o umu resolve) ou um Proton instalado; aí o
    `GAMEID` é o `UMU_ID` do ambiente do jogo, ou o `umu_id` da linha do
    `umu-games.json` (na pasta `runtime/` dos dados dele) com a mesma loja e o
    mesmo id. Qualquer outro caso devolve ``""``: «não sei» é resposta, e uma
    chave que nunca casa é o defeito R-12.

    O que fica de fora, e cai no «não sei»: o `UMU_ID` posto no nível do runner
    ou do sistema (só o do jogo é lido), e o Proton de uma biblioteca da Steam
    fora das pastas de sempre (o Lutris a acharia pelo `libraryfolders.vdf`).
    Uma leitura só do `umu-games.json` e do `runners/wine.yml` por biblioteca.
    """

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
            # A PRIMEIRA LINHA GANHA, como no laço do Lutris.
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
        """O jogo abre pelo umu, e com ele pelo script do Proton?

        O runner `wine` com a versão padrão (`ge-proton`, que o umu resolve) ou
        com uma versão que é um Proton instalado (`is_proton_path` no 0.5.22).
        """
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
    """A pasta de dados do Lutris (o `pga.db`, o `runtime/`), pela regra dele.

    No 0.5.22 (`settings.DATA_DIR`) os dados moram sempre em `data/lutris` no
    Flatpak e em `$XDG_DATA_HOME/lutris` no nativo; a configuração é a mesma
    pasta quando é o atalho para lá (o Flatpak dela, medido em 11/09/2026) ou
    quando a `config/` não existe (:func:`_pastas_lidas`). A de quem usa o
    Lutris desde antes do 0.5.17 é pasta própria, com `runners/` e sem o
    `pga.db` (02/10/2026): por isso os dados vêm antes dela. A casa é a de
    quem chama (:class:`_Onde`), e não deduzida do caminho: com o
    `XDG_DATA_HOME` desviado, a dedução procurava o banco na casa errada e
    caía na pasta de configuração.
    """
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
    """A biblioteca de cada pasta que o censo lê (:func:`pastas_lidas`), cada uma
    com o `onde` dela — para quem escreve na casa do jogo (a carona do Heroic
    escreve no `GamesConfig` da casa de onde o jogo veio). Vazio = nenhuma."""
    if lancador not in _LEITORES:
        return []
    onde = _onde(lar, xdg_config, xdg_data, raiz_sistema)
    return [_ler(lancador, pasta, onde) for pasta in _pastas_lidas(lancador, onde)]


def _uma_vez_por_jogo(jogos: list[JogoDoLancador]) -> list[JogoDoLancador]:
    """Cada jogo do Heroic uma vez, pela loja e pela chave, o instalado na frente.

    **A BIBLIOTECA DO HEROIC É A DA CONTA (02/10/2026, conferência da
    O-CENSO-RESPONDE-COMO-O-LANCADOR-RESPONDE-01).** Com os dois Heroic
    instalados e a mesma conta nos dois, cada casa lista os mesmos jogos, e a
    soma dizia «4 jogos na biblioteca» com dois na conta. O Lutris não entra:
    cada `pga.db` é uma instalação. Quem escreve na casa do jogo (a carona, a
    exclusão) lê cada casa (:func:`bibliotecas_por_casa`), e não esta soma.
    """
    fora: dict[tuple[str, str], JogoDoLancador] = {}
    for jogo in jogos:
        ja = fora.get((jogo.loja, jogo.chave))
        if ja is None or (jogo.instalado and not ja.instalado):
            fora[(jogo.loja, jogo.chave)] = jogo
    return list(fora.values())


def biblioteca_de(lancador: str, lar: Path | None = None, *,
                  xdg_config: Path | None = None, xdg_data: Path | None = None,
                  raiz_sistema: Path | None = None) -> BibliotecaDoLancador:
    """O que este lançador tem na biblioteca — ou por que não se sabe.

    **NUNCA LEVANTA.** A aba pinta a cada tique; uma exceção aqui apagaria a
    coluna inteira por um `.json` truncado. O que não se pôde ler vira
    `ILEGIVEL` com o motivo, que a tela mostra.

    Com os dois programas instalados, as duas casas se somam
    (:func:`_pastas_lidas`), e cada jogo leva a dele (o `.yml` de cada jogo do
    Lutris é o da casa de onde ele veio).

    :param lar: o `HOME` a inspecionar. O padrão é o de verdade; a régua passa
        um lar de mentira — é o que permite medir os cinco leitores sem ter os
        cinco lançadores instalados.
    :param xdg_config: o `XDG_CONFIG_HOME` deste lar (:class:`_Onde`).
    :param xdg_data: o `XDG_DATA_HOME` deste lar.
    :param raiz_sistema: a instalação do Flatpak do sistema; a régua passa uma
        de mentira, para a resposta não depender da máquina em que roda.
    """
    if lancador not in _LEITORES:
        #: NÃO É `NUNCA_ABERTO`: quem não tem leitor pode simplesmente não ter
        #: biblioteca — é o caso do «Flatpak», que é o runtime dos outros. Ver
        #: `SEM_BIBLIOTECA`.
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
    #: Os REGISTROS DE CADA LOJA entraram em 02/10/2026, no lugar do
    #: `*_install_info.json`: é deles que sai o instalado
    #: (:data:`_REGISTROS_DO_HEROIC`), e sem eles a aba Perfis seguiria com a
    #: resposta velha depois de uma instalação.
    "Heroic": ("store_cache/*_library.json", "store_cache/umu.json",
               *(rel for rels in _REGISTROS_DO_HEROIC.values() for rel in rels)),
    #: O `-wal` ENTRA, e é requisito e não zelo: em modo WAL o sqlite escreve
    #: as linhas novas no `pga.db-wal` e pode não tocar no `pga.db`. Quem lê
    #: em `mode=ro` enxerga os dois; a impressão tem de enxergar os dois.
    #: O `runners/wine.yml` e o `umu-games.json` ENTRARAM EM 02/10/2026, com o
    #: degrau 1 do Lutris (`_UmuDoLutris`): a versão do Wine e a tabela do umu
    #: mudam a chave de janela sem tocar no banco. Com a configuração em pasta
    #: própria, o banco e a tabela moram nos dados (`_FONTES_DOS_DADOS_DO_LUTRIS`).
    "Lutris": ("pga.db", "pga.db-wal", "games/*.yml", "runners/wine.yml",
               "runtime/umu-games/umu-games.json"),
    "RetroArch": ("playlists/*.lpl",),
    "Dolphin": ("Dolphin.ini",),
    "mGBA": ("config.ini",),
}

#: O que o Lutris lê da pasta de DADOS quando ela não é a de configuração
#: (`_pasta_de_dados_do_lutris`, 02/10/2026).
_FONTES_DOS_DADOS_DO_LUTRIS = ("pga.db", "pga.db-wal", "runtime/umu-games/umu-games.json")


def _impressao(caminho: Path) -> tuple[str, int, int]:
    """``(caminho, mtime_ns, tamanho)`` de um arquivo ou pasta — e nunca levanta.

    O TAMANHO ENTRA JUNTO porque o `mtime` sozinho tem a resolução do sistema
    de arquivos, e duas escritas dentro do mesmo tique existem — um
    `legendary_library.json` que ganha um jogo muda de tamanho sempre.

    Ausente entra com ``-1`` em vez de sumir da lista: instalar o Lutris (ou
    baixar o primeiro jogo de uma loja, que é quando o registro dela nasce)
    também tem de contar como mudança.
    """
    try:
        st = os.stat(caminho)
    except OSError:
        return (str(caminho), -1, -1)
    return (str(caminho), st.st_mtime_ns, st.st_size)


def assinatura_das_bibliotecas(
    lar: Path | None = None, *,
    xdg_config: Path | None = None, xdg_data: Path | None = None,
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
    """Existe leitor de biblioteca para este lançador?

    É o que separa *"não sei ler"* de *"não há o que ler"* — e é a diferença
    entre o selo velho (`NÃO SEI`) e a frase nova. O cartão «Flatpak» cai
    aqui: ele não é lançador, é o runtime dos outros (§5.4 da sprint).
    """
    return lancador in _LEITORES
