"""As camadas Vulkan implícitas que moram DENTRO do prefixo Wine de cada jogo.

Sprint ENGASGO-VULKAN-01 (23/08/2026). O Sackboy dela entregava **3.597 quadros
por minuto — 60 fps de média perfeita** — e mesmo assim engasgava: **~70 quadros
longos por minuto** (>33 ms, medidos de 47 a 91 ms), um por segundo, com os
vizinhos correndo para compensar. Não é lentidão, é **ritmo de apresentação
desigual**, e o metrônomo tem período de 1,021 s SOLTO do relógio de parede
(qui-quadrado 1 contra 9 graus de liberdade na fase dentro do segundo) — ou
seja, nasce dentro do laço de quadro do jogo, não de temporizador do sistema.

Caiu tudo o que era fácil culpar, cada linha medida: GPU em 51% a 65 °C com
todos os `Clocks Event Reasons` em `Not Active`; oito jogos dela no MESMO
GE-Proton10-34 e só um engasga; engasga com o Hefesto DESLIGADO e com um
jogador só; Mortal Kombat e Wukong no ultra, lisos; e os próprios medidores
saem da conta (69,9/min com eles, 70,7/min sem).

O que sobrou foi a varredura dos **27 prefixos `compatdata`** dela: 26 têm SÓ
`winevulkan.json` — o driver Vulkan do próprio Wine, obrigatório — e **um
único** tem camada a mais, o do Sackboy, com o `EOSOverlayVkLayer` do Epic
Online Services registrado como camada IMPLÍCITA. Camada implícita embrulha a
chamada de apresentação do quadro, o que explica cada observação de uma vez: a
média intacta, a CPU firme, a GPU sem estrangulamento, o período solto do
relógio e o "só neste jogo".

**Grau de confiança: EVIDÊNCIA CONTRÁRIA (23/08/2026, medido).** O A/B saiu, e
derrubou a hipótese. Dois logs por quadro, guardados em
`docs/process/estudos/dados/2026-08-23-frametime-sackboy/`, recomputados por
duas passagens independentes:

    camada LIGADA    104.681 quadros, 30 min: p99 sobe +2,35 ms/min,  51 picos/min
    camada DESLIGADA 111.417 quadros, 36 min: p99 sobe +4,19 ms/min, 121 picos/min

**A rampa acontece nos dois casos**, e desligar mediu PIOR. Ressalva de método:
na sessão sem a camada ela estava jogando e na outra o jogo passou mais tempo
parado — carga diferente, e isso não foi controlado. O que a diferença de carga
NÃO explica é a rampa estar presente dos dois lados.

**Este módulo continua valendo, e por outro motivo.** Camada implícita de
terceiro no caminho de apresentação é coisa que quem usa tem o direito de ver e
de tirar, e antes disto o produto não sabia nem enumerar. O que ele não pode
fazer é prometer cura de engasgo — não há.

Pedido dela, textual: *"faz uma cura universal e coloca isso naqueles botões do
emulação tipo travar próton e coloca essa cura contra o vulcan em todos os
jogos"*. Universal é requisito, não estilo: a regra dela de 14/08/2026 é que
**receita por appid deixa todo jogo novo desprotegido**.

O que este módulo NÃO faz: rede, `sudo`, e nada fora de `compatdata`. Tudo é
arquivo do usuário.


O REGISTRO, e o detalhe que a próxima pessoa vai errar
------------------------------------------------------

As camadas ficam em `system.reg`, texto puro dentro do prefixo, em DUAS chaves
(a de 64 bits e a de 32):

    [Software\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861
    "C:\\\\Program Files (x86)\\\\...\\\\EOSOverlayVkLayer-Win64.json"=dword:00000000

    [Software\\\\Wow6432Node\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861
    "C:\\\\Program Files (x86)\\\\...\\\\EOSOverlayVkLayer-Win32.json"=dword:00000000

**`dword:00000000` significa LIGADA.** O número é a flag de DESABILITAR do
carregador Vulkan, não um interruptor de ligar: zero = "não desabilite" = a
camada carrega; qualquer valor diferente de zero = desligada. É o contrário do
que a intuição diz, está escrito aqui e está escrito de novo em `_LIGADA` lá
embaixo, porque ler errado esta linha inverte a cura inteira.

O driver `winevulkan.json` mora em OUTRA chave — `…\\\\Vulkan\\\\Drivers`, nunca
em `ImplicitLayers`. Ou seja: a separação já é estrutural, e mesmo assim ele é
recusado por nome em `_e_o_driver`, com portão próprio
(`tests/unit/test_a_cura_do_engasgo_nunca_mira_o_driver_do_wine.py`). Um engano
ali não quebra um jogo: quebra TODOS de uma vez.


A RÉGUA: por que lista de PRESERVADOS, e não de conhecidos-ruins
----------------------------------------------------------------

Três desenhos eram possíveis, e a escolha aqui é a lista de **preservados** —
tudo que não é o driver e não está nela é *sobra*, mostrada com nome e jogo
antes de qualquer clique:

- **Lista de conhecidos-ruins** (só o `EOSOverlay`) foi RECUSADA porque é a
  regra dela de 14/08 com outro nome: assim como receita por appid deixa todo
  jogo novo desprotegido, receita por nome de camada deixa toda camada nova
  desprotegida. O overlay da Ubisoft, o da EA, o da Rockstar, o do Discord — cada
  um exigiria mexer no código de novo, e quem paga é quem instalou o jogo de
  amanhã.
- **Lista de preservados** é limitada e muda devagar: é o conjunto de
  ferramentas que alguém instala de PROPÓSITO (medidor de quadro, compositor,
  filtro, gravador, a sobreposição da própria Steam). Ela erra para o lado
  seguro na única direção que sobra — uma ferramenta legítima e nova pode ser
  desligada, e o preço disso é "o meu medidor sumiu", com o produto dizendo o
  nome do que desligou e um clique para devolver. O preço do desenho contrário
  é o jogo engasgando sem ninguém saber por quê, que é exatamente o defeito que
  custou esta madrugada.
- **"Tudo que não é o driver, mostrando antes"** é o que a interface FAZ: o
  diálogo lista jogo por jogo o que achou. A lista de preservados é o que
  decide o que fica de fora da mira; a mostra é o que garante que nada saia às
  escondidas.

A sobreposição da Steam (`SteamOverlayVulkanLayer`) está entre os preservados
por decisão de produto, não por acaso: é ela que dá o Shift+Tab, a captura de
tela e a tela de configuração de controle da Steam. Um produto de CONTROLE que
desliga a tela de controle da Steam se auto-sabota.


ONDE A CURA AGE, e a honestidade sobre o wineserver
---------------------------------------------------

A escrita é no `system.reg`, com backup ao lado (`.bak.hefesto-camadas-<ts>`) e
troca atômica (tmp + `os.replace`). O Wine mantém o registro em MEMÓRIA
enquanto o prefixo está vivo e o regrava ao sair — por isso:

- a interface RECUSA com jogo da Steam aberto (mesmo portão do `proton_pin`);
- o gancho de lançamento escreve ANTES de o Proton subir o `wineserver`
  daquele prefixo, que é o instante certo;
- se ainda assim um `wineserver` sobrescrever, a mudança se perde e o próximo
  lançamento a refaz. A cura é idempotente de propósito para que o pior caso
  seja "não pegou desta vez", nunca um prefixo pela metade.

Este módulo é **100% stdlib de propósito** (mesmo padrão de `proton_pin` e
`steam_launch_options`): o `install.sh` o materializa em
`~/.local/share/hefesto-dualsense4unix/bin/hefesto-camadas` e o
`assets/hefesto-launch.sh` o executa como script avulso, com o `python3` do
SISTEMA, sem o pacote no `sys.path`. Import de irmão só acontece TARDE e com
fallback, e a única função que precisa disso é o censo de todos os prefixos —
o gancho de lançamento recebe o prefixo pronto pela `STEAM_COMPAT_DATA_PATH` e
nunca enumera nada.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

#: O valor de dword que significa **camada LIGADA** (a flag de desabilitar em
#: zero). Repetido aqui, fora do docstring, porque é a linha que inverte a cura
#: inteira se for lida ao contrário.
_LIGADA = 0

#: O valor que gravamos para DESLIGAR. Qualquer não-zero serve para o
#: carregador; `1` é o convencional e é o que fica legível para quem abrir o
#: `system.reg` à mão depois.
_DESLIGADA_DWORD = "00000001"

#: Cabeçalho de seção do `system.reg`: `[Chave\\Com\\Escape] <timestamp>`.
_SECAO_RE = re.compile(r"^\[(?P<chave>.*?)\](?:\s|$)")

#: Uma entrada `"nome"=dword:XXXXXXXX` dentro de uma seção.
_ENTRADA_DWORD_RE = re.compile(
    r'^(?P<prefixo>"(?P<nome>(?:\\.|[^"\\])*)"=dword:)(?P<valor>[0-9a-fA-F]+)(?P<sufixo>\s*)$'
)

#: As duas chaves de camadas implícitas (64 e 32 bits), já DESESCAPADAS.
CHAVES_DE_CAMADAS: tuple[str, ...] = (
    r"Software\Khronos\Vulkan\ImplicitLayers",
    r"Software\Wow6432Node\Khronos\Vulkan\ImplicitLayers",
)

#: O driver Vulkan do próprio Wine. **Nunca entra na mira, em nenhum caminho.**
#: Ele vive em `…\Vulkan\Drivers`, não em `ImplicitLayers` — a recusa por nome
#: aqui é o cinto por cima do suspensório, e tem portão só dela.
NOME_DO_DRIVER_DO_WINE = "winevulkan.json"

#: Camadas legítimas e desejadas: pedaços de ferramenta que alguém instala de
#: PROPÓSITO. Casamento por substring, sem acento e em minúsculas, contra o
#: NOME DO ARQUIVO do manifesto. Cada linha tem dono declarado, porque lista
#: sem dono vira lixo em três meses.
CAMADAS_PRESERVADAS: tuple[tuple[str, str], ...] = (
    ("winevulkan", "driver Vulkan do Wine"),
    ("wineopenxr", "OpenXR do Wine"),
    ("steamoverlay", "sobreposição da Steam (Shift+Tab, captura, tela de controle)"),
    ("steam_overlay", "sobreposição da Steam"),
    ("fossilize", "pré-cache de shader da Steam"),
    ("mangohud", "MangoHud — medidor de quadro"),
    ("gamescope", "gamescope — compositor da Valve"),
    ("reshade", "ReShade — filtro de imagem"),
    ("dxvk", "DXVK (HUD, config, NVAPI)"),
    ("vkd3d", "VKD3D-Proton"),
    ("obs_vkcapture", "OBS — captura de tela do jogo"),
    ("obs-vkcapture", "OBS — captura de tela do jogo"),
    ("vkbasalt", "vkBasalt — filtro de imagem"),
    ("optimus", "NVIDIA Optimus"),
    ("nvidia", "camada da NVIDIA"),
    ("amd_switchable", "AMD switchable graphics"),
)

#: Sufixo do estado local. Guarda o que NÓS mexemos e, principalmente, o que
#: ela mandou manter — é ele que impede o gancho de desfazer a escolha dela no
#: lançamento seguinte.
ESTADO_BASENAME = "camadas-vulkan.json"

#: Marca do backup, no molde do `proton_pin` (`.bak.hefesto-proton-<ts>`).
_BACKUP_SUFIXO = ".bak.hefesto-camadas-"


# --------------------------------------------------------------------------
# Escape do registro do Wine
# --------------------------------------------------------------------------


def desescapar(valor: str) -> str:
    """Desfaz o escape do `system.reg` (`\\\\` e `\\"`).

    Mesmo critério do `_desescapar_acf` do `steam_launch_options`: o registro
    do Wine escapa a barra invertida e a aspa, e nada mais aparece nos nomes de
    caminho que nos interessam.
    """
    return valor.replace('\\\\', '\\').replace('\\"', '"')


def _escapar(valor: str) -> str:
    """Refaz o escape do `system.reg`. Inverso exato de `desescapar`.

    **Privada de propósito, e a razão importa:** o produto NUNCA reescapa nada.
    A escrita em `_reescrever` reaproveita o texto original da entrada
    (`entrada.group("prefixo")`) e troca só os dígitos do dword, justamente
    para não depender de reproduzir byte a byte o escape que o Wine escreveu.
    Quem chama isto é o construtor de `system.reg` de mentira dos testes, que
    precisa do inverso PROVADO do parser — se fosse pública, seria promessa
    sem chamador, e o portão `portao_a_casa_sabe_e_o_produto_nao_faz.py` a
    acusaria com razão.
    """
    return valor.replace('\\', '\\\\').replace('"', '\\"')


# --------------------------------------------------------------------------
# Classificação de uma camada
# --------------------------------------------------------------------------


def _e_o_driver(caminho_windows: str) -> bool:
    """`True` para o `winevulkan.json`, em qualquer caixa e qualquer pasta.

    Desligar o driver Vulkan do Wine não quebra UM jogo: quebra todos de uma
    vez, e a pessoa fica sem imagem sem saber o que aconteceu. Por isso a
    recusa é por NOME e não por chave de registro — mesmo que um dia alguém
    registre o driver no lugar errado, ele continua fora da mira.
    """
    return _nome_do_arquivo(caminho_windows) == NOME_DO_DRIVER_DO_WINE


def _nome_do_arquivo(caminho_windows: str) -> str:
    """Último componente de um caminho do Windows, em minúsculas."""
    bruto = caminho_windows.replace("/", "\\").rsplit("\\", 1)[-1]
    return bruto.strip().lower()


def dono_preservado(caminho_windows: str) -> str | None:
    """Quem é o dono desta camada, se ela está entre as preservadas.

    Devolve a descrição legível (para a interface poder dizer POR QUE não
    mexeu) ou `None` quando a camada é uma sobra desconhecida.
    """
    nome = _nome_do_arquivo(caminho_windows)
    for pedaco, dono in CAMADAS_PRESERVADAS:
        if pedaco in nome:
            return dono
    return None


@dataclass(frozen=True)
class Camada:
    """Uma linha de `ImplicitLayers` já interpretada.

    `ligada` é o que o registro diz; `presente` é o que o DISCO diz. Os dois
    juntos cobrem o estado em que a máquina dela estava quando esta leva foi
    escrita: registro apontando para um manifesto que foi renomeado à mão
    (`.json.desligado`), ou seja, entrada VIVA no registro e INERTE
    na prática. Chamar isso de "ligada" seco seria mentira de instrumento.
    """

    caminho_windows: str
    chave: str
    valor: str
    ligada: bool
    presente: bool
    arquivo: Path | None
    preservada_por: str | None

    @property
    def nome_curto(self) -> str:
        """O nome do arquivo do manifesto, que é o que cabe numa linha de tela."""
        return self.caminho_windows.replace("/", "\\").rsplit("\\", 1)[-1]

    @property
    def e_o_driver(self) -> bool:
        """Atalho de leitura — a recusa de verdade mora em `_e_o_driver`."""
        return _e_o_driver(self.caminho_windows)

    @property
    def e_sobra(self) -> bool:
        """Sobra = candidata à cura: nem driver, nem preservada, e LIGADA.

        Entrada já desligada não é sobra: não há o que curar nela, e contá-la
        faria o produto prometer trabalho que não existe.
        """
        return self.ligada and not self.e_o_driver and self.preservada_por is None


@dataclass(frozen=True)
class PrefixoDeJogo:
    """Um `compatdata/<appid>` com o que foi lido do `system.reg` dele."""

    appid: str
    raiz: Path
    registro: Path
    camadas: tuple[Camada, ...]
    nome: str | None = None

    @property
    def sobras(self) -> tuple[Camada, ...]:
        """As camadas que a cura desligaria."""
        return tuple(c for c in self.camadas if c.e_sobra)

    @property
    def rotulo(self) -> str:
        """`Nome do jogo (appid)` — ou só o appid quando não há manifest."""
        return f"{self.nome} ({self.appid})" if self.nome else self.appid


# --------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------


def caminho_no_prefixo(prefixo: Path, caminho_windows: str) -> Path | None:
    """Traduz `C:\\...` para o caminho Linux dentro do prefixo.

    `prefixo` é o `compatdata/<appid>`. `C:` é `pfx/drive_c`; `Z:` é a raiz do
    sistema. Qualquer outra letra devolve `None` — inventar um caminho para
    poder dizer "não existe" seria pior que admitir que não sabemos.
    """
    bruto = caminho_windows.replace("/", "\\")
    if len(bruto) < 2 or bruto[1] != ":":
        return None
    letra = bruto[0].lower()
    resto = bruto[2:].lstrip("\\")
    partes = [p for p in resto.split("\\") if p]
    if letra == "c":
        return prefixo.joinpath("pfx", "drive_c", *partes)
    if letra == "z":
        return Path("/").joinpath(*partes)
    return None


def ler_camadas(registro: Path, *, prefixo: Path | None = None) -> tuple[Camada, ...]:
    """Lê as duas seções `ImplicitLayers` de um `system.reg`.

    Varredura de uma passada e sem regex sobre o arquivo inteiro: o
    `system.reg` do Sackboy tem 5,5 MB e 100 mil linhas, e este código roda no
    caminho do LANÇAMENTO do jogo. Best-effort read-only — arquivo ausente ou
    ilegível devolve tupla vazia, porque "não consegui ler" e "não tem camada"
    levam ao mesmo lugar seguro: não mexer.
    """
    try:
        texto = registro.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    base = prefixo if prefixo is not None else registro.parent.parent
    achadas: list[Camada] = []
    chave_atual: str | None = None
    for linha in texto.splitlines():
        if linha.startswith("["):
            secao = _SECAO_RE.match(linha)
            crua = desescapar(secao.group("chave")) if secao is not None else ""
            chave_atual = crua if crua in CHAVES_DE_CAMADAS else None
            continue
        if chave_atual is None or not linha.startswith('"'):
            continue
        entrada = _ENTRADA_DWORD_RE.match(linha)
        if entrada is None:
            continue
        caminho = desescapar(entrada.group("nome"))
        arquivo = caminho_no_prefixo(base, caminho)
        try:
            presente = arquivo is not None and arquivo.exists()
        except OSError:  # pragma: no cover - permissão negada no meio do caminho
            presente = False
        achadas.append(
            Camada(
                caminho_windows=caminho,
                chave=chave_atual,
                valor=entrada.group("valor"),
                ligada=int(entrada.group("valor"), 16) == _LIGADA,
                presente=presente,
                arquivo=arquivo,
                preservada_por=dono_preservado(caminho),
            )
        )
    return tuple(achadas)


def prefixo_de_jogo(
    raiz: Path, *, appid: str | None = None, nome: str | None = None
) -> PrefixoDeJogo:
    """Monta o `PrefixoDeJogo` de um `compatdata/<appid>` já localizado."""
    registro = raiz / "pfx" / "system.reg"
    return PrefixoDeJogo(
        appid=appid if appid is not None else raiz.name,
        raiz=raiz,
        registro=registro,
        camadas=ler_camadas(registro, prefixo=raiz),
        nome=nome,
    )


def _pastas_steamapps_do_irmao() -> Callable[[Path | None], list[Path]] | None:
    """O `pastas_steamapps` do irmão, ou `None` quando ele não está alcançável.

    Import TARDE e nas duas formas: `from .steam_launch_options` quando o
    pacote está montado, e `import steam_launch_options` quando este arquivo
    roda de dentro da pasta `integrations/`. Na cópia avulsa instalada em
    `~/.local/share/.../bin/hefesto-camadas` nenhuma das duas resolve, e aí a
    resposta honesta é `None` — não uma lista vazia disfarçada de resultado.
    """
    try:
        from .steam_launch_options import pastas_steamapps
    except ImportError:  # pragma: no cover - cópia avulsa, sem o pacote
        try:
            from steam_launch_options import pastas_steamapps  # type: ignore[no-redef]
        except ImportError:
            return None
    return pastas_steamapps


def sabe_enumerar() -> bool:
    """Esta cópia consegue LISTAR os jogos, ou só curar um prefixo apontado?

    Existe para que o relatório não diga "não achei camada nenhuma" quando a
    verdade é "não consegui abrir a lista de jogos". Medido em 23/08/2026: a
    cópia avulsa instalada respondia exatamente essa mentira, que é a armadilha
    número um desta casa — *o instrumento mente mais que o produto*.
    """
    return _pastas_steamapps_do_irmao() is not None


def pastas_compatdata(home: Path | None = None) -> list[Path]:
    """Todo `steamapps/compatdata` desta máquina, biblioteca por biblioteca.

    **Reusa `steam_launch_options.pastas_steamapps`, não reescreve.** Aquele
    módulo é o dono do formato VDF nesta casa e já resolve o que morde aqui:
    biblioteca em outro disco pelo `libraryfolders.vdf` (nesta máquina,
    `/mnt/Mnemosyne/SteamLibrary`) e a mesma `steamapps` chegando por dois
    caminhos de texto diferentes — `~/.steam/steam` é link para
    `~/.steam/debian-installation`, e comparar texto contava tudo em dobro
    (BIBLIOTECA-DOBRADA-01, 16/08/2026).

    Import TARDE e com fallback pelo motivo do cabeçalho: quando este arquivo
    roda como cópia avulsa em `~/.local/share/.../bin/hefesto-camadas`, o
    irmão não está no `sys.path`. Nesse caso a lista sai VAZIA — e é
    `sabe_enumerar` que separa esse "não consegui olhar" do "olhei e não achou
    nada", porque as duas coisas devolvem `[]` e confundi-las é o instrumento
    mentindo. O gancho de lançamento não passa por aqui: ele recebe o prefixo
    pronto pela `STEAM_COMPAT_DATA_PATH`.
    """
    if not sabe_enumerar():
        return []
    pastas_steamapps = _pastas_steamapps_do_irmao()
    assert pastas_steamapps is not None
    saida: list[Path] = []
    for steamapps in pastas_steamapps(home):
        candidata = steamapps / "compatdata"
        if candidata.is_dir():
            saida.append(candidata)
    return saida


def _nome_do_appid(appid: str, home: Path | None = None) -> str | None:
    """Nome do jogo pelo `appmanifest`, reusando o dono do formato."""
    try:
        from .steam_launch_options import nome_do_appid
    except ImportError:  # pragma: no cover - cópia avulsa, sem o pacote
        try:
            from steam_launch_options import nome_do_appid  # type: ignore[no-redef]
        except ImportError:
            return None
    try:
        return nome_do_appid(appid, home)
    except Exception:  # pragma: no cover - tradução é conveniência, nunca gate
        return None


def censo(home: Path | None = None, *, com_nomes: bool = True) -> list[PrefixoDeJogo]:
    """Todos os prefixos, com as camadas de cada um. Read-only.

    Só volta prefixo que TEM alguma camada implícita registrada: na máquina
    dela isso é 1 de 27, e listar os 26 vazios seria enterrar o achado no
    ruído. Quem precisa da contagem total usa `pastas_compatdata`.
    """
    saida: list[PrefixoDeJogo] = []
    for pasta in pastas_compatdata(home):
        try:
            entradas = sorted(pasta.iterdir())
        except OSError:
            continue
        for raiz in entradas:
            if not raiz.name.isdigit() or not raiz.is_dir():
                continue
            achado = prefixo_de_jogo(raiz)
            if not achado.camadas:
                continue
            if com_nomes:
                achado = PrefixoDeJogo(
                    appid=achado.appid,
                    raiz=achado.raiz,
                    registro=achado.registro,
                    camadas=achado.camadas,
                    nome=_nome_do_appid(achado.appid, home),
                )
            saida.append(achado)
    saida.sort(key=lambda p: int(p.appid))
    return saida


# --------------------------------------------------------------------------
# Estado local — o que mexemos e, sobretudo, o que ela mandou MANTER
# --------------------------------------------------------------------------


def caminho_do_estado(home: Path | None = None) -> Path:
    """`~/.local/state/hefesto-dualsense4unix/camadas-vulkan.json`."""
    base = home or Path.home()
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    state_home = Path(xdg) if xdg and home is None else base / ".local/state"
    return state_home / "hefesto-dualsense4unix" / ESTADO_BASENAME


def ler_estado(home: Path | None = None) -> dict[str, dict[str, dict[str, str]]]:
    """Lê o estado local. Arquivo ausente ou torto devolve dicionário vazio."""
    try:
        dados = json.loads(caminho_do_estado(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    prefixos = dados.get("prefixos") if isinstance(dados, dict) else None
    if not isinstance(prefixos, dict):
        return {}
    limpo: dict[str, dict[str, dict[str, str]]] = {}
    for appid, camadas in prefixos.items():
        if not isinstance(camadas, dict):
            continue
        limpo[str(appid)] = {
            str(k): v for k, v in camadas.items() if isinstance(v, dict)
        }
    return limpo


def gravar_estado(
    prefixos: dict[str, dict[str, dict[str, str]]], home: Path | None = None
) -> None:
    """Grava o estado local (tmp + replace). Falha aqui NUNCA derruba a cura."""
    alvo = caminho_do_estado(home)
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        tmp = alvo.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"formato": 1, "prefixos": prefixos}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, alvo)
    except OSError:
        return


def _agora() -> str:
    """Carimbo legível, hora local, sem dependência externa."""
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def chave_de_estado(chave: str, caminho_windows: str) -> str:
    """Identidade de UMA entrada no estado local: a chave do registro E o caminho.

    O caminho sozinho NÃO identifica uma entrada — o mesmo manifesto pode estar
    registrado na chave de 64 bits e na de 32 com valores diferentes, e foi
    exatamente isso que quebrou a reversibilidade byte a byte antes de
    23/08/2026 (o `valor_antes` do segundo sobrescrevia o do primeiro, e
    devolver restaurava os dois para o mesmo número). O motivo longo está em
    `_reescrever`.

    O separador é `|` porque o Windows o PROÍBE em nome de arquivo e de pasta,
    e as duas chaves de registro são constantes deste módulo — nenhum dos dois
    lados pode contê-lo, então a junção nunca fica ambígua.
    """
    return f"{chave}|{caminho_windows}"


# --------------------------------------------------------------------------
# Escrita no registro
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Resultado:
    """O que a cura fez num prefixo — é isto que a interface transforma em frase."""

    appid: str
    desligadas: tuple[str, ...] = ()
    religadas: tuple[str, ...] = ()
    respeitadas: tuple[str, ...] = ()
    erro: str = ""

    @property
    def mexeu(self) -> bool:
        """Houve escrita? Usado para decidir se vale gravar estado e avisar."""
        return bool(self.desligadas or self.religadas)


def _reescrever(registro: Path, alvos: dict[tuple[str, str], str]) -> None:
    """Troca o dword das entradas nomeadas em `alvos`, e só delas.

    `alvos` é `{(chave_do_registro, caminho_windows_desescapado): novo_dword}`.
    A troca só vale DENTRO das duas seções de `ImplicitLayers`: um caminho que
    apareça em outra chave do registro (o driver em `…\\Vulkan\\Drivers` é o
    caso real) passa intocado, por construção e não por sorte.

    **A chave entra no alvo, e isso é correção de defeito medido (23/08/2026),
    não zelo.** Enquanto o alvo era só o caminho, `alvos.get(caminho)` casava
    a MESMA linha nas DUAS seções — e o mesmo manifesto pode estar registrado
    na chave de 64 e na de 32 bits com valores DIFERENTES. Medido num prefixo
    de mentira: entrada de 64 em `dword:00000000` (ligada, candidata) e a de 32
    em `dword:00000003` (já desligada, classificada `e_sobra=False`); curar
    escrevia `00000001` nas DUAS, inclusive na que o próprio módulo tinha dito
    que não ia tocar, e devolver trazia as duas para `00000000` — ou seja, a
    reversibilidade byte a byte quebrava e a segunda entrada saía LIGADA sem
    nunca ter estado. Portão:
    `test_o_mesmo_manifesto_nas_duas_chaves_nao_contamina_a_outra`.

    Backup ao lado, escrita em tmp e `os.replace` no fim — o `system.reg` não
    pode existir pela metade nem por um instante, porque o Wine pode lê-lo a
    qualquer momento.
    """
    texto = registro.read_text(encoding="utf-8", errors="replace")
    saida: list[str] = []
    chave_atual: str | None = None
    quebra = "\r\n" if "\r\n" in texto else "\n"
    for linha in texto.split(quebra):
        if linha.startswith("["):
            secao = _SECAO_RE.match(linha)
            crua = desescapar(secao.group("chave")) if secao is not None else ""
            chave_atual = crua if crua in CHAVES_DE_CAMADAS else None
            saida.append(linha)
            continue
        if chave_atual is None or not linha.startswith('"'):
            saida.append(linha)
            continue
        entrada = _ENTRADA_DWORD_RE.match(linha)
        if entrada is None:
            saida.append(linha)
            continue
        caminho = desescapar(entrada.group("nome"))
        novo = alvos.get((chave_atual, caminho))
        if novo is None:
            saida.append(linha)
            continue
        saida.append(f"{entrada.group('prefixo')}{novo}{entrada.group('sufixo')}")
    backup = registro.with_name(f"{registro.name}{_BACKUP_SUFIXO}{int(time.time())}")
    shutil.copy2(registro, backup)
    tmp = registro.with_name(f"{registro.name}.hefesto-tmp")
    tmp.write_text(quebra.join(saida), encoding="utf-8")
    os.replace(tmp, registro)


def aplicar_no_prefixo(
    prefixo: PrefixoDeJogo,
    *,
    religar: bool = False,
    forcar: bool = False,
    home: Path | None = None,
) -> Resultado:
    """Desliga (ou religa) as camadas sobrando deste prefixo.

    Três regras, e as três são pedido dela:

    1. **A escolha dela vence a automação.** Camada marcada `manter` no estado
       local nunca é desligada de novo — é o que impede o gancho de lançamento
       de desfazer, no jogo seguinte, o que ela religou de propósito.
    2. **Religar por fora também conta como escolha.** Se o registro mostra
       LIGADA uma camada que NÓS desligamos, alguém a religou sem passar por
       aqui: a resposta é marcar `manter` e sair, não desligar de novo. Sem
       esta regra a pessoa que edita o registro à mão brigaria com o produto
       para sempre.
    3. **Gesto explícito na interface manda.** `forcar=True` (o botão) limpa o
       `manter` e desliga — "a vontade da GUI prevalece", regra dela de
       09/08/2026. O gancho de lançamento nunca força.
    """
    estado = ler_estado(home)
    memoria = dict(estado.get(prefixo.appid, {}))
    alvos: dict[tuple[str, str], str] = {}
    desligadas: list[str] = []
    religadas: list[str] = []
    respeitadas: list[str] = []

    if religar:
        for camada in prefixo.camadas:
            marca = chave_de_estado(camada.chave, camada.caminho_windows)
            registro_dela = memoria.get(marca, {})
            if camada.ligada or registro_dela.get("feito") != "desligada":
                continue
            alvos[(camada.chave, camada.caminho_windows)] = registro_dela.get(
                "valor_antes", "00000000"
            )
            religadas.append(camada.nome_curto)
            memoria[marca] = {
                "feito": "religada",
                "escolha": "manter",
                "quando": _agora(),
            }
    else:
        for camada in prefixo.camadas:
            if not camada.e_sobra:
                continue
            marca = chave_de_estado(camada.chave, camada.caminho_windows)
            registro_dela = memoria.get(marca, {})
            if not forcar and registro_dela.get("escolha") == "manter":
                respeitadas.append(camada.nome_curto)
                continue
            if not forcar and registro_dela.get("feito") == "desligada":
                # Nós desligamos e ela está LIGADA de novo: alguém religou por
                # fora. Vira escolha, não vira briga.
                memoria[marca] = {
                    "feito": "religada-por-fora",
                    "escolha": "manter",
                    "quando": _agora(),
                }
                respeitadas.append(camada.nome_curto)
                continue
            alvos[(camada.chave, camada.caminho_windows)] = _DESLIGADA_DWORD
            desligadas.append(camada.nome_curto)
            memoria[marca] = {
                "feito": "desligada",
                "valor_antes": camada.valor,
                "quando": _agora(),
            }

    if not alvos:
        if respeitadas:
            estado[prefixo.appid] = memoria
            gravar_estado(estado, home)
        return Resultado(appid=prefixo.appid, respeitadas=tuple(respeitadas))

    # Cinto: nem por engano de chamador o driver do Wine entra na escrita.
    for _chave, caminho in alvos:
        if _e_o_driver(caminho):
            return Resultado(
                appid=prefixo.appid,
                erro=f"recusei mexer no driver do Wine ({caminho})",
            )

    try:
        _reescrever(prefixo.registro, alvos)
    except OSError as exc:
        return Resultado(appid=prefixo.appid, erro=str(exc))

    estado[prefixo.appid] = memoria
    gravar_estado(estado, home)
    return Resultado(
        appid=prefixo.appid,
        desligadas=tuple(desligadas),
        religadas=tuple(religadas),
        respeitadas=tuple(respeitadas),
    )


def curar_todos(
    home: Path | None = None, *, religar: bool = False, forcar: bool = True
) -> list[Resultado]:
    """Passa em todos os prefixos desta máquina. É o que o botão chama."""
    return [
        aplicar_no_prefixo(p, religar=religar, forcar=forcar, home=home)
        for p in censo(home)
        if p.camadas
    ]


def curar_um_prefixo(
    raiz: Path, *, appid: str | None = None, home: Path | None = None
) -> Resultado:
    """A entrada do gancho de lançamento: um prefixo, sem enumerar nada.

    Nunca força — a escolha dela sobrevive ao próximo lançamento (regra 3 de
    `aplicar_no_prefixo`). `home` existe só para o teste poder montar uma casa
    inteira em `tmp_path`; em produção fica `None` e o estado sai do XDG.
    """
    prefixo = prefixo_de_jogo(raiz, appid=appid)
    if not prefixo.sobras:
        return Resultado(appid=prefixo.appid)
    return aplicar_no_prefixo(prefixo, forcar=False, home=home)


# --------------------------------------------------------------------------
# CLI — usada pelo gancho de lançamento, pelo install/uninstall e pelo doctor
# --------------------------------------------------------------------------


def _linha_de_relatorio(prefixo: PrefixoDeJogo) -> list[str]:
    """As linhas de UM prefixo no relatório de texto."""
    linhas = [f"{prefixo.rotulo}:"]
    for camada in prefixo.camadas:
        if camada.e_o_driver:
            estado = "driver do Wine — fora da mira"
        elif camada.preservada_por is not None:
            estado = f"preservada ({camada.preservada_por})"
        elif not camada.ligada:
            estado = "desligada"
        elif not camada.presente:
            estado = "registrada, mas o arquivo não está no disco — inerte"
        else:
            estado = "LIGADA — candidata"
        linhas.append(f"    {camada.nome_curto}: {estado}")
    return linhas


def main(argv: list[str] | None = None) -> int:
    """CLI stdlib. `--relatorio` é read-only; os outros escrevem."""
    parser = argparse.ArgumentParser(
        description="Camadas Vulkan implícitas nos prefixos Wine dos jogos."
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--relatorio", action="store_true", help="censo read-only")
    grupo.add_argument("--curar", action="store_true", help="desliga as sobras")
    grupo.add_argument("--devolver", action="store_true", help="religa o que desligamos")
    grupo.add_argument(
        "--prefixo",
        metavar="CAMINHO",
        help="cura UM compatdata/<appid> (usado pelo gancho de lançamento)",
    )
    parser.add_argument(
        "--appid", default=None, help="appid, quando o caminho não o revelar"
    )
    args = parser.parse_args(argv)

    if args.prefixo:
        # `--appid ""` chega assim do gancho de lançamento quando a Steam não
        # exportou `SteamAppId`; vazio vira `None` para o nome do diretório
        # valer, em vez de gravar o estado sob uma chave em branco.
        resultado = curar_um_prefixo(Path(args.prefixo), appid=args.appid or None)
        if resultado.erro:
            print(f"erro: {resultado.erro}", file=sys.stderr)
            return 1
        if resultado.desligadas:
            print("desligadas: " + ", ".join(resultado.desligadas))
        return 0

    if not sabe_enumerar():
        # A cópia avulsa instalada não alcança o irmão que lê o
        # `libraryfolders.vdf`, e sem ele não há lista de jogos. Dizer "não
        # achei nada" aqui seria mentira do instrumento; o modo `--prefixo`,
        # que é o do gancho de lançamento, continua inteiro porque não enumera.
        print(
            "esta cópia não consegue listar os jogos (falta o módulo irmão "
            "steam_launch_options); só o modo --prefixo funciona aqui",
            file=sys.stderr,
        )
        return 2

    if args.relatorio:
        achados = censo()
        if not achados:
            print("nenhum prefixo com camada Vulkan implícita registrada")
            return 0
        for prefixo in achados:
            for linha in _linha_de_relatorio(prefixo):
                print(linha)
        return 0

    resultados = curar_todos(religar=bool(args.devolver))
    mexidos = [r for r in resultados if r.mexeu or r.erro]
    if not mexidos:
        print("nada a mudar")
        return 0
    for resultado in mexidos:
        if resultado.erro:
            print(f"{resultado.appid}: erro: {resultado.erro}", file=sys.stderr)
            continue
        acao = "religadas" if args.devolver else "desligadas"
        nomes = resultado.religadas if args.devolver else resultado.desligadas
        print(f"{resultado.appid}: {acao}: " + ", ".join(nomes))
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de script avulso
    raise SystemExit(main())
