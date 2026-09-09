"""O que o Flatpak deixa entrar no lançador — LANCADORES-ZERO-01 §5.4, 09/09/2026.

**O CARTÃO «FLATPAK» NÃO TEM BIBLIOTECA, E A PERGUNTA DELE É OUTRA.** Ele não é
lançador: é o RUNTIME dos outros cinco. Enquanto ele respondia a pergunta dos
outros, o cartão dizia `LOCALIZADO` e mais nada — uma linha com um travessão
sobre o programa que decide se o controle chega a QUALQUER jogo desta máquina.

A pergunta que só ele sabe responder é a da §4 da sprint: **o controle virtual
entra na caixa em que o jogo roda?** Um flatpak só vê o que a permissão dele
deixa ver, e o controle do Hefesto é um nó do kernel (`/dev/input`,
`/dev/hidraw`) — sem a permissão de dispositivo, o jogo dentro da caixa não o
enxerga, por mais certo que esteja tudo o mais.

ONDE A RESPOSTA MORA, e são DOIS arquivos por aplicativo
--------------------------------------------------------

    <lar>/.local/share/flatpak/app/<id>/current/active/metadata   o que o
                                                                 pacote pede
    /var/lib/flatpak/app/<id>/current/active/metadata             o mesmo, na
                                                                 instalação do
                                                                 sistema
    /var/lib/flatpak/overrides/global                             o que o
    /var/lib/flatpak/overrides/<id>                               sistema mudou
    <lar>/.local/share/flatpak/overrides/global                   o que ELA
    <lar>/.local/share/flatpak/overrides/<id>                     mudou depois

O valor está em ``[Context] devices=``, separado por ``;``, e o override SOMA
ao do pacote — com ``!`` na frente para TIRAR (medido no disco dela em
09/09/2026: ``org.bleachbit.BleachBit`` traz
``filesystems=!xdg-data/applications;``). Um override que ela tenha feito é a
resposta mais nova, e ignorá-lo daria verde sobre uma caixa fechada à mão.

**MEDIDO NA MÁQUINA DELA, 09/09/2026** — os cinco lançadores instalados como
flatpak, todos do lado do usuário (``/var/lib/flatpak/app`` nem existe):

    com.heroicgameslauncher.hgl   devices=all;
    net.lutris.Lutris             devices=all;
    org.libretro.RetroArch        devices=all;
    org.DolphinEmu.dolphin-emu    devices=all;
    io.mgba.mGBA                  devices=all;

É o que a §4 da sprint afirmava tendo medido com ``flatpak info
--show-permissions``, e este módulo o responde **sem chamar o binário**: são
`read_text()` do `metadata` e dos overrides que existirem, dentro do tique de
uma aba, contra um subprocesso por aplicativo que a janela pagaria dez vezes
por segundo.

POR QUE NÃO CHAMAR ``flatpak``
-------------------------------

Porque o produto não precisa dele para saber isto, e porque um subprocesso é
uma dependência a mais para dar a MESMA resposta: o `flatpak` lê exatamente
estes arquivos. Quem tiver de escrever (a cura, `cura_por_estrada`) escreve o
arquivo de override — que é o mesmo que ``flatpak override --user --env=…``
escreve, e no mesmo formato.
"""
from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

#: A PERMISSÃO QUE ABRE TUDO — `--device=all`. É a que os cinco lançadores dela
#: trazem, e a que a Flathub dá a todo lançador de jogo, porque um jogo pode
#: querer qualquer controle.
TODOS = "all"

#: **A PERMISSÃO ESTREITA, e ela BASTA para o controle** — `--device=input`
#: abre `/dev/input`, que é onde o controle virtual do Hefesto aparece para o
#: jogo. O que ela NÃO abre é o caminho cru do aparelho; para o controle do
#: Hefesto isso não muda nada, porque o que o jogo lê é o virtual.
#:
#: SÃO DUAS RESPOSTAS DIFERENTES E UMA CONCLUSÃO SÓ, e é por isso que as duas
#: entram aqui em vez de o código comparar com `"all"` e pronto: uma caixa com
#: `input` deixa o controle entrar, e reprová-la seria o produto dizendo "não
#: chega" sobre um jogo em que ele chega.
ENTRADA = "input"

#: O QUE SE SABE DE UMA CAIXA. `NAO_INSTALADO` não é reprovação: é o Flatpak
#: respondendo que aquele aplicativo não está instalado por ele — o caso do
#: lançador nativo, que não tem caixa nenhuma e por isso não tem o que abrir.
ENTRA = "entra"
NAO_ENTRA = "nao_entra"
NAO_INSTALADO = "nao_instalado"

#: A MARCA DE QUE UM ATALHO VEIO DO FLATPAK, no caminho do próprio `.desktop`:
#: `…/flatpak/exports/share/applications/<app-id>.desktop`. É o que separa o
#: lançador que roda numa caixa do que roda solto — e ele é MEDIDO, não
#: adivinhado pelo nome: `net.lutris.Lutris` pode estar instalado pelo `apt`
#: com o mesmo rótulo no cartão, e aí não há caixa a examinar.
_MARCA_DO_EXPORT = "flatpak/exports/"


def app_id_do_atalho(onde: str | Path | None) -> str:
    """O `app-id` do flatpak que publicou este `.desktop`, ou `""`.

    **A PERGUNTA É SOBRE O CAMINHO, E NÃO SOBRE O NOME.** Um `.desktop` em
    `~/.local/share/flatpak/exports/share/applications/io.mgba.mGBA.desktop` é
    de um flatpak; o mesmo nome em `/usr/share/applications` é do pacote da
    distribuição, que não tem caixa. Derivar o `app-id` do rótulo do cartão
    diria "caixa fechada" sobre um programa que não está numa.
    """
    if not onde:
        return ""
    texto = str(onde)
    if _MARCA_DO_EXPORT not in texto or not texto.endswith(".desktop"):
        return ""
    return Path(texto).stem


def _ini(caminho: Path) -> configparser.ConfigParser | None:
    """O arquivo lido, ou `None` — e NUNCA levanta.

    `interpolation=None` NÃO É ZELO: a seção `[Environment]` de um override
    guarda valores com `%` (um `WINEPREFIX`, um `MANGOHUD_CONFIG`), e o
    `configparser` padrão tenta interpolá-los e explode no `read`. Foi assim
    que o dela quase não pôde ser lido — `QT_WAYLAND_DECORATION=adwaita` passa,
    mas o próximo valor não passaria.

    `optionxform=str` PRESERVA A CAIXA DAS CHAVES. O padrão minúsculo
    transformaria `SDL_JOYSTICK_HIDAPI` em `sdl_joystick_hidapi` — e quem lê
    este arquivo para reescrevê-lo (`cura_por_estrada`) gravaria a chave errada
    de volta no disco dela.
    """
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    cfg.optionxform = str  # type: ignore[method-assign,assignment]
    try:
        cfg.read_string(caminho.read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error):
        return None
    return cfg


def _lista(cfg: configparser.ConfigParser | None, secao: str, chave: str
           ) -> list[str]:
    """Os itens de um valor `a;b;c;` do Flatpak, sem os vazios."""
    if cfg is None or not cfg.has_option(secao, chave):
        return []
    return [x.strip() for x in cfg.get(secao, chave).split(";") if x.strip()]


@dataclass(frozen=True)
class Permissao:
    """O que a caixa de UM aplicativo deixa entrar.

    `porque` é a frase para quem investiga — ela NÃO vai para a tela: nomear
    `/dev/input` numa janela é a língua de dentro, que o glossário desta casa
    proíbe em texto de tela.
    """

    app_id: str
    estado: str = NAO_INSTALADO
    dispositivos: tuple[str, ...] = ()
    onde: Path | None = None
    porque: str = ""

    @property
    def entra(self) -> bool:
        return self.estado == ENTRA


def _raizes(lar: Path, raiz_sistema: Path | None) -> tuple[Path, Path]:
    return (lar / ".local/share/flatpak",
            Path("/var/lib/flatpak") if raiz_sistema is None else raiz_sistema)


def permissao_de(app_id: str, lar: Path | None = None,
                 raiz_sistema: Path | None = None) -> Permissao:
    """A caixa deste aplicativo: o que o pacote pede **mais** o que ela mudou.

    **NUNCA LEVANTA.** Ela é chamada de dentro do tique de uma aba, e um
    `metadata` truncado não pode apagar o cartão.

    A ORDEM É A DO FLATPAK: o `metadata` do pacote é a base, o `overrides/global`
    vem por cima e o `overrides/<id>` por último — o mais específico ganha. Uma
    entrada com `!` na frente TIRA a permissão, e é a única forma de a resposta
    ficar negativa numa máquina em que o pacote pediu `all`.
    """
    lar = Path.home() if lar is None else lar
    usuario, sistema = _raizes(lar, raiz_sistema)
    meta = None
    onde: Path | None = None
    for raiz in (usuario, sistema):
        tentativa = raiz / "app" / app_id / "current/active/metadata"
        if tentativa.is_file():
            meta, onde = _ini(tentativa), tentativa
            break
    if meta is None:
        return Permissao(app_id, NAO_INSTALADO, (), None,
                         "não está instalado pelo Flatpak nesta máquina")
    tem = list(_lista(meta, "Context", "devices"))
    #: A ORDEM É A DO FLATPAK, do mais geral para o mais específico: o
    #: `global` da instalação do sistema, o do aplicativo lá, e depois os dois
    #: do lado do usuário. **A do sistema entra mesmo sem `/var/lib/flatpak`
    #: existir** (é o caso da máquina dela, medido em 09/09/2026): os quatro
    #: caminhos passam pelo mesmo `is_file()`, e o que não existe é pulado.
    #: Lê-los é o que impede o produto de dar verde sobre uma caixa que o
    #: administrador da máquina fechou.
    for arq in (sistema / "overrides/global", sistema / "overrides" / app_id,
                usuario / "overrides/global", usuario / "overrides" / app_id):
        if not arq.is_file():
            continue
        for item in _lista(_ini(arq), "Context", "devices"):
            if item.startswith("!"):
                tem = [x for x in tem if x != item[1:]]
            elif item not in tem:
                tem.append(item)
    if TODOS in tem:
        return Permissao(app_id, ENTRA, tuple(tem), onde,
                         "devices=all — a caixa abre todos os dispositivos")
    if ENTRADA in tem:
        return Permissao(app_id, ENTRA, tuple(tem), onde,
                         "devices=input — a caixa abre /dev/input, que é onde "
                         "o controle virtual aparece")
    return Permissao(app_id, NAO_ENTRA, tuple(tem), onde,
                     "devices não traz `all` nem `input` — nenhum controle "
                     "atravessa esta caixa")


def app_ids_instalados(atalhos: tuple[str, ...], lar: Path | None = None,
                       raiz_sistema: Path | None = None) -> tuple[str, ...]:
    """Os `app-id` desta lista que o Flatpak instalou NESTA máquina.

    A LISTA DE ATALHOS NÃO É A RESPOSTA, e é isso que faz o cartão duplo
    funcionar: «Dolphin · mGBA» traz os DOIS `app-id` mais os dois nomes
    nativos (`dolphin-emu`, `mgba-qt`), e só os que têm caixa no disco existem
    como flatpak. Quem separa é o disco, não o formato do nome — embora o ponto
    seja um filtro barato que evita um `is_file()` por nome de comando.
    """
    fora: list[str] = []
    for a in atalhos:
        if "." not in a or a in fora:
            continue
        if permissao_de(a, lar, raiz_sistema).estado != NAO_INSTALADO:
            fora.append(a)
    return tuple(fora)


def app_ids_do_cartao(atalhos: tuple[str, ...], onde: str | Path | None = None,
                      lar: Path | None = None,
                      raiz_sistema: Path | None = None) -> tuple[str, ...]:
    """As caixas que UM cartão da aba 07 representa.

    DUAS FONTES, E A ORDEM É A DA FORÇA. Primeiro o `.desktop` que a aba
    ACHOU: ele é o programa que ela realmente vai abrir, medido pela busca do
    produto. Depois os demais `atalhos` com caixa no disco — porque **um cartão
    pode ser dois programas**, e o achado devolve UM caminho só.

    **MEDIDO EM 09/09/2026, e foi assim que o defeito apareceu:** o cartão
    «Dolphin · mGBA» foi achado pelo `.desktop` do Dolphin, e o cartão «Flatpak»
    respondeu *"4 lançadores por aqui"* numa máquina com CINCO. O mGBA existia,
    tinha caixa e não entrava na conta porque ninguém perguntou por ele.
    """
    fora = [x for x in (app_id_do_atalho(onde),) if x]
    for a in app_ids_instalados(atalhos, lar, raiz_sistema):
        if a not in fora:
            fora.append(a)
    return tuple(fora)


@dataclass(frozen=True)
class RespostaDoFlatpak:
    """O que o cartão «Flatpak» diz — a soma das caixas dos lançadores achados.

    ELA É A ÚNICA MONTADORA DA FRASE, pela mesma razão de
    `censo_dos_lancadores.BibliotecaDoLancador.resumo`: duas montagens
    divergem no dia em que a contagem mudar de forma.
    """

    permissoes: tuple[Permissao, ...] = ()

    @property
    def dentro(self) -> tuple[Permissao, ...]:
        """As que o Flatpak instalou — as únicas sobre as quais há o que dizer."""
        return tuple(p for p in self.permissoes if p.estado != NAO_INSTALADO)

    @property
    def fechadas(self) -> tuple[Permissao, ...]:
        return tuple(p for p in self.dentro if not p.entra)

    @property
    def resumo(self) -> str:
        """A linha do cartão. Vazia quando não há lançador nenhum em caixa.

        **VAZIA É RESPOSTA**, e é o mesmo cuidado do `SEM_BIBLIOTECA`: numa
        máquina onde os lançadores são nativos, o Flatpak não tem sobre o que
        se pronunciar, e uma frase ali seria o produto respondendo por um
        mundo que não existe naquela máquina.

        A PALAVRA É A DA TELA, e não a de dentro: «caixa» e não *sandbox*,
        «controle» e não *vpad*, e nenhuma menção a `/dev`. O glossário desta
        casa (`docs/A-LINGUA-DESTA-CASA`) proíbe a língua de dentro em texto de
        tela, e este é texto de tela.
        """
        n = len(self.dentro)
        if not n:
            return ""
        fechadas = self.fechadas
        if not fechadas:
            return (f"{n} {'lançador' if n == 1 else 'lançadores'} por aqui, "
                    f"e o controle entra em {'todos' if n > 1 else 'ele'}")
        return (f"{n - len(fechadas)} de {n} deixam o controle entrar")


def resposta_do_flatpak(app_ids: tuple[str, ...], lar: Path | None = None,
                        raiz_sistema: Path | None = None) -> RespostaDoFlatpak:
    """As caixas dos lançadores que a aba ACHOU, na ordem em que ela os achou.

    :param app_ids: os `app-id` vindos de :func:`app_id_do_atalho`, um por
        cartão localizado. **Quem não veio do Flatpak não entra na lista** —
        perguntar pela caixa de um programa nativo devolveria `NAO_INSTALADO` e
        baixaria a conta do cartão por um motivo que não é dela.
    """
    vistos: list[str] = []
    for a in app_ids:
        if a and a not in vistos:
            vistos.append(a)
    return RespostaDoFlatpak(tuple(permissao_de(a, lar, raiz_sistema)
                                   for a in vistos))
