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
* **nunca escreve fora da allowlist** (`daemon.launch_env.ENV_ALLOWLIST`). O
  arquivo do daemon é lido por um wrapper `sh` que filtra por essa lista
  justamente contra arquivo adulterado; a mesma lista filtra aqui.
"""
from __future__ import annotations

import configparser
import contextlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from hefesto_dualsense4unix.integrations import sandbox_dos_lancadores as _caixa
from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

#: AS DUAS ESTRADAS. O nome é o do ARQUIVO que se escreve, e não o do lançador:
#: quem ganhar uma terceira estrada amanhã (um lançador nativo com config
#: própria) acrescenta um valor aqui, e não um `if` no meio da escrita.
HEROIC_CONFIG = "heroic-config"
FLATPAK_OVERRIDE = "flatpak-override"

#: A CHAVE DO HEROIC, com a grafia DELE. `enviromentOptions` — sem o segundo
#: `n` — é como o Heroic gravou desde sempre, e foi lida assim no `config.json`
#: dela em 09/09/2026. Corrigir a grafia aqui escreveria uma chave que o
#: Heroic não lê: seria a cura silenciosa, que é pior que nenhuma.
CHAVE_DO_HEROIC = "enviromentOptions"

#: A subpasta de configuração do Heroic, dentro do flatpak ou do lar nativo —
#: a mesma que `censo_dos_lancadores._pasta_de_config` acha.
_HEROIC_APP_ID = "com.heroicgameslauncher.hgl"

#: A FRASE DA RECUSA SEM AMBIENTE. Ela nomeia o que falta e o que fazer, e não
#: menciona arquivo nenhum: «ambiente», «serviço» e «controle» são as palavras
#: da tela; `default.env` é a língua de dentro.
SEM_AMBIENTE = ("O serviço ainda não publicou o ambiente desta sessão. Ligue o "
                "Hefesto, conecte um controle e tente de novo.")

#: A FRASE DA RECUSA SOBRE UM ARQUIVO QUE NÃO ABRE — e ela existe para o
#: produto NÃO reescrever configuração dela por cima de um arquivo que ele não
#: entendeu. Ver :func:`_ler_heroic`.
ILEGIVEL = ("Não consegui ler o `{arquivo}` deste lançador, e não vou "
            "reescrevê-lo por cima. Abra o lançador uma vez e tente de novo.")


def ambiente_da_ponte(pasta: Path | None = None) -> dict[str, str]:
    """O ambiente que o daemon publicou para ESTA sessão — ou `{}`.

    É o `default.env`: o que o wrapper exportaria para um jogo sem perfil
    próprio, que é exatamente o caso de todo jogo dos outros lançadores (nenhum
    tem `steam_app_<id>`). Ler o do daemon em vez de recalcular é o que impede
    duas contas para a mesma pergunta.

    **NUNCA LEVANTA, e `{}` é resposta:** quem chama trata o vazio como recusa
    (:data:`SEM_AMBIENTE`). Um `{}` escrito no disco dela apagaria o ambiente
    que já estivesse lá, que é o contrário da cura.

    O IMPORT DA ALLOWLIST É TARDIO, e é estrutural: `daemon/launch_env.py` puxa
    o daemon inteiro, e este módulo é lido pelo DESENHO da aba 07 — que o
    gerador `aba07.py` importa rodando como script solto, fora da instalação.
    Um import no topo faria o gerador arrastar o daemon para desenhar um botão.
    A lista continua tendo UM dono; só a hora de perguntar a ele mudou.
    """
    from hefesto_dualsense4unix.daemon.launch_env import ENV_ALLOWLIST

    alvo = (launch_env_dir() if pasta is None else pasta) / "default.env"
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


@dataclass(frozen=True)
class Estrada:
    """Por onde o ambiente entra NESTE lançador."""

    cartao: str
    tipo: str
    arquivo: Path
    #: Só nas estradas de override — o `app-id` da caixa que recebe o ambiente.
    app_id: str = ""


@dataclass(frozen=True)
class Plano:
    """O que a cura FARIA, antes de fazer.

    ELE EXISTE SEPARADO DA ESCRITA de propósito: a tela precisa saber se há
    botão a oferecer (`tem_estrada`) sem tocar em disco dela, e a régua precisa
    medir a decisão sem exercitar a escrita.
    """

    cartao: str
    estradas: tuple[Estrada, ...] = ()
    ambiente: dict[str, str] = field(default_factory=dict)
    impedimento: str = ""
    #: O NOME QUE A TELA MOSTRA (*"Heroic (Epic · GOG)"*), e não a chave
    #: interna. **MEDIDO NA TELA VIVA em 09/09/2026:** sem ele a tarja dizia
    #: *"Ajustei o ambiente de heroic"* — a chave do `data-lancador` na frente
    #: dela, que é a língua de dentro num recado de tela.
    nome: str = ""

    @property
    def rotulo(self) -> str:
        """O que a TELA chama este cartão. A chave interna é a queda."""
        return self.nome or self.cartao


def _pasta_do_heroic(lar: Path) -> Path | None:
    """A pasta de configuração do Heroic — flatpak primeiro, nativo depois."""
    for tentativa in (lar / ".var/app" / _HEROIC_APP_ID / "config/heroic",
                      lar / ".config/heroic"):
        if tentativa.is_dir():
            return tentativa
    return None


def estradas_do_cartao(chave: str, atalhos: tuple[str, ...],
                       lar: Path | None = None,
                       raiz_sistema: Path | None = None) -> tuple[Estrada, ...]:
    """Por onde a cura entra neste cartão. Vazio = não há estrada aqui.

    O HEROIC TEM ESTRADA PRÓPRIA e não ganha override, e a escolha é dele, não
    minha: o Heroic MONTA o ambiente do jogo a partir do
    `enviromentOptions` — escrever nos dois lugares poria a mesma variável em
    duas listas que envelhecem separadas, e a próxima pessoa não saberia qual
    manda.

    A STEAM NÃO ENTRA AQUI. Ela tem o atalho de inicialização, que é a estrada
    dela, e um override por cima seria a segunda entrega do mesmo ambiente.
    """
    lar = Path.home() if lar is None else lar
    if chave == "steam":
        return ()
    if chave == "heroic":
        pasta = _pasta_do_heroic(lar)
        if pasta is None:
            return ()
        return (Estrada(chave, HEROIC_CONFIG, pasta / "config.json"),)
    raiz = lar / ".local/share/flatpak/overrides"
    #: QUEM SABE QUAIS CAIXAS ESTE CARTÃO TEM é o `sandbox_dos_lancadores` —
    #: a mesma função que o cartão «Flatpak» usa para contar. Duas listas de
    #: `app-id`, uma para contar e outra para escrever, divergiriam no dia em
    #: que um cartão ganhasse um segundo programa dentro — que é exatamente o
    #: que o «Dolphin · mGBA» é.
    return tuple(Estrada(chave, FLATPAK_OVERRIDE, raiz / a, a)
                 for a in _caixa.app_ids_instalados(atalhos, lar, raiz_sistema))


def planejar(chave: str, atalhos: tuple[str, ...], lar: Path | None = None,
             pasta_do_ambiente: Path | None = None,
             raiz_sistema: Path | None = None, nome: str = "") -> Plano:
    """O que a cura faria neste cartão — sem escrever um byte.

    :param nome: o rótulo do cartão, para a frase da tela. Sem ele a frase sai
        com a chave interna, que é a língua de dentro num recado dela.
    """
    estradas = estradas_do_cartao(chave, atalhos, lar, raiz_sistema)
    if not estradas:
        return Plano(chave, (), {}, "não há por onde entrar neste lançador",
                     nome)
    ambiente = ambiente_da_ponte(pasta_do_ambiente)
    if not ambiente:
        return Plano(chave, estradas, {}, SEM_AMBIENTE, nome)
    return Plano(chave, estradas, ambiente, "", nome)


def tem_estrada(chave: str, atalhos: tuple[str, ...],
                lar: Path | None = None,
                raiz_sistema: Path | None = None) -> bool:
    """Há botão a oferecer neste cartão? — a pergunta da VIGIA.

    Ela NÃO olha o ambiente de propósito. Um botão que some quando o serviço
    está desligado seria a tela escondendo a cura justamente de quem está
    tentando entender por que o controle não chega; o botão fica, e a recusa
    (:data:`SEM_AMBIENTE`) diz o que ligar.

    **ELA ABRE DISCO**, e por isso quem pergunta é `desenho.medir_no_disco`, na
    thread da vigia — nunca a pintura do tique.

    O `raiz_sistema` VIAJA COM O `lar` desde 09/09/2026: sem ele, uma régua com
    lar de mentira ainda ia ler `/var/lib/flatpak` no disco de verdade, e a
    resposta dela dependia da máquina em que rodasse.
    """
    return bool(estradas_do_cartao(chave, atalhos, lar, raiz_sistema))


def _modo_de_nascimento(pasta: Path) -> int:
    """O modo de um arquivo que NASCE nesta pasta — herdado dela.

    **NÃO SE LÊ O `umask` AQUI, e a razão é de thread:** `os.umask` é a única
    forma de consultá-lo pela biblioteca padrão, e consultar é ESCREVER (põe
    zero e devolve o valor). Esta escrita roda na thread de um gesto, com a
    janela viva ao lado; um arquivo que outra thread abrisse naquela janelinha
    nasceria com a permissão errada.

    A PASTA CARREGA A MESMA INTENÇÃO: `~/.local/share/flatpak/overrides` a
    0755 devolve 0644, e uma pasta fechada a 0700 devolve 0600. É o que o
    `flatpak override` produz nas duas máquinas, sem perguntar nada ao processo.
    """
    try:
        return stat.S_IMODE(pasta.stat().st_mode) & 0o666
    except OSError:  # pragma: no cover - a pasta acabou de ser criada
        return 0o644


def _escrever_atomico(alvo: Path, texto: str) -> None:
    """Grava por arquivo temporário no MESMO diretório, e então renomeia.

    Configuração dela: um `write_text` interrompido no meio deixaria o
    `config.json` do Heroic truncado, e o Heroic abriria sem a biblioteca. O
    temporário vizinho garante que ou o arquivo velho está inteiro, ou o novo
    está.

    **E ELE DEVOLVE O MODO E O DONO DO ARQUIVO DELA — 09/09/2026, e sem isto a
    troca era silenciosa.** `NamedTemporaryFile` nasce **0600** (é o contrato
    dele, contra arquivo temporário bisbilhotado), e `replace()` leva o modo do
    TEMPORÁRIO junto: o `config.json` do Heroic dela, medido a **0644** antes
    da cura, ficava **0600** depois. Este módulo promete *"nunca apaga o que já
    estava lá"*, e a permissão de um arquivo é parte do que estava lá — um
    override a 0600 deixa de ser legível por um serviço que rode com outro
    usuário, e ninguém liga isso ao clique de ontem.

    O DONO VAI JUNTO **quando dá**: um `chown` para o mesmo usuário é sempre
    permitido, e para outro usuário só com privilégio que este produto não tem
    (e não quer). O `OSError` é o caso normal, não a exceção — por isso ele
    passa em silêncio: o arquivo continua inteiro, com o modo certo.
    """
    alvo.parent.mkdir(parents=True, exist_ok=True)
    #: O ANTES SE MEDE ANTES DE ESCREVER, e não depois: `replace()` já terá
    #: destruído o modo original quando alguém pensar em perguntar por ele.
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
    """O `config.json` do Heroic, `{}` se ele não existe, `None` se ILEGÍVEL.

    **OS TRÊS CASOS SÃO DIFERENTES, e confundir dois deles APAGA a configuração
    dela.** Um arquivo que existe e não abre pode estar truncado por um Heroic
    que morreu no meio de um `write` — e reescrevê-lo com `{}` mais o nosso
    ambiente jogaria fora a biblioteca, o caminho do Wine e tudo o mais. Quem
    não sabe ler não pode escrever: ver :func:`escrever_a_estrada`.
    """
    if not alvo.exists():
        return {}
    try:
        dado = cast("object", json.loads(alvo.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None
    return dado if isinstance(dado, dict) else None


def _escrever_no_heroic(alvo: Path, ambiente: dict[str, str]) -> None:
    """Funde o ambiente em `defaultSettings.enviromentOptions`.

    O QUE JÁ ESTAVA LÁ FICA. A lista é de `{key, value}`; as nossas substituem
    as de mesmo `key` e as demais seguem na ordem em que estavam — um
    `MANGOHUD=1` dela não pode sumir porque o Hefesto passou por ali.
    """
    raiz = _ler_heroic(alvo) or {}
    padroes = raiz.get("defaultSettings")
    if not isinstance(padroes, dict):
        padroes = {}
    velhas = padroes.get(CHAVE_DO_HEROIC)
    lista: list[dict[str, str]] = [
        {"key": str(x.get("key", "")), "value": str(x.get("value", ""))}
        for x in (velhas if isinstance(velhas, list) else [])
        if isinstance(x, dict) and str(x.get("key", "")) not in ambiente
    ]
    lista += [{"key": k, "value": v} for k, v in sorted(ambiente.items())]
    padroes[CHAVE_DO_HEROIC] = lista
    raiz["defaultSettings"] = padroes
    _escrever_atomico(alvo, json.dumps(raiz, indent=2, ensure_ascii=False) + "\n")


def _render_ini(cfg: configparser.ConfigParser) -> str:
    """O arquivo de override como o Flatpak o escreve — `chave=valor`, sem espaço.

    NÃO SE USA `ConfigParser.write`, e a razão é de FORMATO: ele emite
    `chave = valor`, com espaços, e o arquivo é lido pelo `GKeyFile` do Flatpak.
    Escrever num formato que o dono do arquivo não emite é convidar o dia em que
    ele deixa de ler — num arquivo de configuração dela, e sem aviso.
    """
    partes: list[str] = []
    for secao in cfg.sections():
        partes.append(f"[{secao}]")
        partes += [f"{k}={v}" for k, v in cfg.items(secao)]
        partes.append("")
    return "\n".join(partes).rstrip("\n") + "\n"


def _ler_override(alvo: Path) -> configparser.ConfigParser | None:
    """O override deste aplicativo, vazio se não existe, `None` se ILEGÍVEL.

    A MESMA DISCIPLINA DE :func:`_ler_heroic`, e pela mesma razão: um override
    que existe e não abre pode ter a `[Context]` inteira dela lá dentro, e
    reescrevê-lo só com o nosso `[Environment]` tiraria do aplicativo o acesso
    que ela deu à mão.
    """
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    cfg.optionxform = str  # type: ignore[method-assign,assignment]
    if not alvo.exists():
        return cfg
    try:
        cfg.read_string(alvo.read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error):
        return None
    return cfg


def _escrever_no_override(alvo: Path, ambiente: dict[str, str]) -> None:
    """Põe o ambiente em `[Environment]`, preservando todo o resto do arquivo.

    É O MESMO ARQUIVO de `flatpak override --user --env=NOME=VALOR`, e por isso
    ele continua reversível pelo caminho dela: `flatpak override --user --reset`
    apaga o arquivo inteiro, e `--unset-env=NOME` tira uma linha.
    """
    cfg = _ler_override(alvo)
    if cfg is None:  # pragma: no cover - `escrever_a_estrada` já recusou antes
        raise RuntimeError(ILEGIVEL.format(arquivo=alvo.name))
    if not cfg.has_section("Environment"):
        cfg.add_section("Environment")
    for nome, valor in sorted(ambiente.items()):
        cfg.set("Environment", nome, valor)
    _escrever_atomico(alvo, _render_ini(cfg))


def frase_do_feito(plano: Plano) -> str:
    """O recibo que a tela mostra — e ele diz o que mudou, onde e o que fazer.

    **A PALAVRA É A DO GLOSSÁRIO DESTA CASA.** «ambiente» sozinho não diz nada
    a quem clica; o que o `docs/A-LINGUA-DESTA-CASA` já usa para este fato é
    *"faz o jogo enxergar o controle pelo Hefesto"*, na linha do atalho de
    inicialização. É o mesmo fato por outra estrada, e por isso a mesma frase.

    **SEM ARTIGO ANTES DO NOME**, pela razão que a
    `desenho_dos_lancadores.NOVO_PARA_O_CARTAO` já mediu em 08/09/2026: o nome
    vem do cartão — inclusive de um que ELA acrescentou —, e adivinhar o gênero
    de um nome que ainda não existe é palpite na tela dela.

    UMA MONTADORA SÓ, e ela é pública porque a régua a lê. Montar a frase
    dentro da escrita obrigaria a régua a escrever num arquivo para saber o que
    a tela diria.
    """
    n = len(plano.ambiente)
    k = len(plano.estradas)
    quantos = f"os {k} programas " if k > 1 else ""
    cada = " em cada" if k > 1 else ""
    return (f"{plano.rotulo}: ajustei {quantos}para o jogo enxergar o controle "
            f"pelo Hefesto — {n} {'ajuste' if n == 1 else 'ajustes'}{cada}. "
            "Feche e abra o lançador para valer.")


def escrever_a_estrada(plano: Plano) -> str:
    """Escreve o ambiente nas estradas do plano e diz o que escreveu.

    **RECUSA LEVANTANDO**, que é o contrato desta casa para "o produto não
    fez": um retorno mudo viraria piscada verde sobre um arquivo que ninguém
    tocou. A frase da recusa é a que a tela mostra.

    A FRASE DE SUCESSO DIZ O QUE FOI ESCRITO E ONDE — não *"pronto"*. Ela é a
    única prova que ela tem, sem abrir um terminal, de que o clique alcançou
    alguma coisa; e é o que a régua lê para saber que a escrita aconteceu.
    """
    if plano.impedimento:
        raise RuntimeError(plano.impedimento)
    if not plano.estradas:
        raise RuntimeError("não há por onde entrar neste lançador")
    if not plano.ambiente:
        raise RuntimeError(SEM_AMBIENTE)
    #: **NINGUÉM ESCREVE ANTES DE TODOS SEREM LEGÍVEIS.** Um cartão pode ter
    #: DUAS estradas, e recusar no meio do laço deixaria uma escrita e a outra
    #: não, com a tela mostrando só a recusa — o pior dos dois mundos. A
    #: conferência inteira vem primeiro; depois é só escrever.
    for estrada in plano.estradas:
        legivel = (_ler_heroic(estrada.arquivo) if estrada.tipo == HEROIC_CONFIG
                   else _ler_override(estrada.arquivo))
        if legivel is None:
            raise RuntimeError(ILEGIVEL.format(arquivo=estrada.arquivo.name))
    for estrada in plano.estradas:
        if estrada.tipo == HEROIC_CONFIG:
            _escrever_no_heroic(estrada.arquivo, plano.ambiente)
        else:
            _escrever_no_override(estrada.arquivo, plano.ambiente)
    return frase_do_feito(plano)
