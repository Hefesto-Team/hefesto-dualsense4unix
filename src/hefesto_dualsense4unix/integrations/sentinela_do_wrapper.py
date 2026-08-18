"""Sentinela do wrapper de launch: o produto percebe quando a Steam o apaga.

SENTINELA-WRAPPER-01 — 16/08/2026, defeito pego AO VIVO.

O QUE ACONTECEU
---------------
Ela jogou Pragmata (appid 3357650) no CABO e funcionou. Passou para o
Bluetooth e, nas palavras dela: *"no inicio travou alguns inputs mas logo em
sequencia ele parou de ser reconhecido no jogo, mas o perfil de pragmata segue
ativo no controle com tudo funcionando só não sendo reconhecido"*.

O daemon estava SAUDÁVEL o tempo todo — vpad P1 com os quatro nós, grab retido
(`grab=True ok=True state=held`), `launch_env/steam_app_3357650.env`
materializado com o conteúdo certo. Ele fez a parte dele. O arquivo nunca foi
lido, **porque quem o lê é o wrapper, e o wrapper não rodou**.

As Opções de Inicialização do Pragmata eram::

    VKD3D_CONFIG=no_upload_hvv %command%

e as dos outros SESSENTA jogos dela eram a chamada do `hefesto-launch`. A
Steam guarda **UMA linha por jogo**: quando o `VKD3D_CONFIG` foi posto (quase
certo que para curar o crash de 14/08), ele SUBSTITUIU o wrapper. Ninguém
percebeu, porque a Steam não avisa e o campo aceita qualquer texto.

A cadeia do estrago, medida no `/proc` do jogo rodando:

1. o wrapper não rodou ⇒ `PROTON_DISABLE_HIDRAW` no ambiente do jogo: **zero**
   (só o Hefesto escreve essa variável);
2. o `SDL_GAMECONTROLLER_IGNORE_DEVICES` que chegou ao jogo não era o nosso —
   era a lista gigante da própria Steam;
3. e dentro dela está `0x054c/0x0df2`, o PID do NOSSO vpad, ao lado do
   `0x054c/0x0ce6`, o do físico: o jogo foi instruído a ignorar OS DOIS;
4. resultado: `event21` (o vpad) — ninguém abriu; `event25` (o físico) — a
   Steam abriu. O jogo ficou sem nenhum. No cabo funcionava porque ali ele
   alcança o aparelho por outro caminho.

O modo de falha é o mais confuso que existe: o controle continua vivo, a luz
acesa, o perfil aplicado — e só o JOGO não enxerga. Sem esta sentinela, o
único jeito de descobrir é o que ela fez: perder uma noite de jogo.

O QUE ESTE MÓDULO FAZ, em três camadas independentes
----------------------------------------------------
1. **DETECTAR** (`censo_do_wrapper`) — quais jogos da biblioteca têm a chamada
   do wrapper e quais não têm, a qualquer momento. O `localconfig.vdf` é
   legível com a Steam aberta; só a ESCRITA é que não pode.
2. **AVISAR** (`frase_do_aviso`) — a frase pronta, com o NOME do jogo, para a
   GUI e para o doctor. Diagnóstico que não chega na tela não existe.
3. **REPARAR** (`reparar_ou_adiar`) — repõe o wrapper PRESERVANDO o que já
   estava na linha, ou ADIA dizendo por quê.

A COMPOSIÇÃO QUE PRESERVA A LINHA DELA (medida, não suposta)
-------------------------------------------------------------
O reparo do Pragmata tem de manter o wrapper **e** o `VKD3D_CONFIG` — soltar
um dos dois troca um defeito por outro. A linha que o `migrate_value` já emite
faz exatamente isso::

    sh -c 'W="$HOME/…/hefesto-launch"; [ -x "$W" ] && exec "$W" "$@";
        exec env "$@"' hefesto-launch VKD3D_CONFIG=no_upload_hvv %command%

e ela funciona porque o wrapper termina em ``exec env "$@"``: o
`VKD3D_CONFIG=no_upload_hvv` chega como argumento do `env(1)`, que o trata
como assignment. Executado de verdade em 16/08/2026, com wrapper de mentira e
jogo de mentira, o jogo recebeu as três variáveis (`VKD3D_CONFIG`,
`PROTON_DISABLE_HIDRAW`, `SDL_GAMECONTROLLER_IGNORE_DEVICES`) e os argumentos
originais intactos; com o wrapper AUSENTE, recebeu o `VKD3D_CONFIG` e abriu do
mesmo jeito. **Não é preciso — nem se deve — intercalar um `env` extra antes
do `VKD3D_CONFIG`**: a composição de duas camadas já é a certa, e é a mesma
que os outros 60 jogos usam. Inventar uma segunda forma de escrever a linha
quebraria a idempotência (o `WRAPPER_PREFIX in value` deixaria de casar) —
e com ela, 60 jogos de uma vez.

AS QUATRO PERGUNTAS DO DESENHO, e a resposta de cada uma
--------------------------------------------------------
- **"E se ela tirar o wrapper DE PROPÓSITO?"** — Intenção nunca é inferida. A
  única voz que conta é o `jogos_sem_wrapper.txt` (`marcar_jogo_sem_wrapper`,
  um clique na GUI): esses jogos somem do aviso E do reparo, inclusive do
  passo sem flag do install. Uma linha que sumiu sozinha é sempre tratada como
  estrago — a Steam sobrescreve sem avisar, e é o caso comum.
- **"E se a Steam puser LaunchOptions sozinha num jogo novo?"** — O registro
  (`wrapper-visto.json`) guarda os appids que JÁ foram vistos com o wrapper.
  Jogo que nunca esteve lá é ``novo``; jogo que estava e sumiu é
  ``regressao``. Os dois são reparados (é o que o install já faz com todo
  mundo), mas só a regressão ganha a frase *"parou de funcionar"* — que é a
  informação que ela não tinha.
- **"O reparo é idempotente?"** — Sim, e não por promessa: ele delega ao
  `apply_wrapper_to_all_games`, cujo gate `WRAPPER_PREFIX in value` pula quem
  já tem. Rodar dez vezes é igual a rodar uma.
- **"Há backup?"** — Sim, o mesmo do caminho em massa: um
  `.bak.hefesto-launch-<ts>` ao lado de cada vdf tocado, antes de escrever,
  com `tmp` + `replace`. O `localconfig.vdf` guarda a biblioteca inteira dela.

A STEAM ABERTA
--------------
A Steam regrava o `localconfig.vdf` ao sair e **engole** qualquer edição feita
por baixo. O reparo por isso detecta e ADIA (`adiado_steam_aberta`), e com um
JOGO aberto adia antes mesmo disso (`adiado_jogo_aberto` — fechar a Steam ali
mataria o jogo). Não há marcador de pendência em disco de propósito: o censo é
uma leitura de arquivo, então basta rodá-lo de novo depois. Estado guardado
sobre um vdf que muda sozinho envelheceria errado — e mentir sobre isso é o
que esta sentinela existe para não fazer.

Módulo 100% stdlib, como os vizinhos `steam_launch_options` e `proton_pin`: o
`doctor.sh` o roda com o `python3` do sistema, sem venv.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

try:  # importado como módulo do pacote (GUI/daemon/testes)
    from .steam_launch_options import (
        WRAPPER_PREFIX,
        apply_wrapper_to_all_games,
        discover_vdfs,
        has_extended_ignore,
        is_sandboxed_layout,
        juntar_rotulos,
        ler_jogos_sem_wrapper,
        read_apps_by_appid,
        rotulo_do_jogo,
        steam_game_running,
        steam_running,
    )
except ImportError:  # pragma: no cover - executado como script avulso pelo doctor
    from steam_launch_options import (  # type: ignore[no-redef]
        WRAPPER_PREFIX,
        apply_wrapper_to_all_games,
        discover_vdfs,
        has_extended_ignore,
        is_sandboxed_layout,
        juntar_rotulos,
        ler_jogos_sem_wrapper,
        read_apps_by_appid,
        rotulo_do_jogo,
        steam_game_running,
        steam_running,
    )

#: Registro dos appids já vistos COM o wrapper. É o que separa "perdeu" de
#: "nunca teve" — e a razão de ele viver em estado local, e não dentro do vdf,
#: é a mesma do `proton-pin-lock.json`: marcador dentro do vdf não sobrevive à
#: Steam, que regrava o arquivo ao sair.
REGISTRO_BASENAME = "wrapper-visto.json"

#: Motivo de um jogo estar sem o wrapper.
MOTIVO_REGRESSAO = "regressao"       #: já teve o wrapper e PERDEU (o Pragmata)
MOTIVO_NOVO = "novo"                 #: nunca teve (jogo novo na biblioteca)
MOTIVO_ESTENDIDO = "ignore_estendido"  #: linha INTOCÁVEL — só reparo manual

#: Status de `reparar_ou_adiar`.
REPARO_NADA = "nada_a_fazer"
REPARO_FEITO = "reparado"
REPARO_ADIADO_JOGO = "adiado_jogo_aberto"
REPARO_ADIADO_STEAM = "adiado_steam_aberta"
REPARO_ERRO = "erro"


@dataclass(frozen=True)
class JogoSemWrapper:
    """Um jogo cuja linha de Opções de Inicialização não chama o wrapper."""

    appid: str
    rotulo: str
    #: A LaunchOptions atual, crua. `None` = o jogo nem tem a linha.
    opcoes: str | None
    motivo: str
    vdf: str


@dataclass(frozen=True)
class Censo:
    """Fotografia read-only do estado do wrapper na biblioteca inteira."""

    com_wrapper: list[str] = field(default_factory=list)
    faltantes: list[JogoSemWrapper] = field(default_factory=list)
    #: appids que ela recusou explicitamente (`jogos_sem_wrapper.txt`).
    recusados: list[str] = field(default_factory=list)
    #: vdfs pulados por inteiro (Flatpak/Snap: o wrapper do host é invisível).
    sandbox: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    steam_aberta: bool = False
    jogo_aberto: bool = False

    @property
    def regressoes(self) -> list[JogoSemWrapper]:
        """Os que TINHAM o wrapper e perderam — o defeito confuso do Pragmata."""
        return [j for j in self.faltantes if j.motivo == MOTIVO_REGRESSAO]

    @property
    def novos(self) -> list[JogoSemWrapper]:
        """Os que nunca tiveram — jogo novo, ou biblioteca nunca aplicada."""
        return [j for j in self.faltantes if j.motivo == MOTIVO_NOVO]

    @property
    def intocaveis(self) -> list[JogoSemWrapper]:
        """Linhas com a lista de IGNORE estendida: mexer quebraria o launch."""
        return [j for j in self.faltantes if j.motivo == MOTIVO_ESTENDIDO]

    @property
    def reparaveis(self) -> list[JogoSemWrapper]:
        """O que o `reparar_ou_adiar` de fato consegue consertar sozinho."""
        return [j for j in self.faltantes if j.motivo != MOTIVO_ESTENDIDO]

    def como_dicionario(self) -> dict[str, object]:
        """Forma JSON — é o que o `doctor.sh` consome (`--censo`)."""
        return {
            "com_wrapper": list(self.com_wrapper),
            "faltantes": [
                {
                    "appid": j.appid,
                    "rotulo": j.rotulo,
                    "launch_options": j.opcoes,
                    "motivo": j.motivo,
                    "vdf": j.vdf,
                }
                for j in self.faltantes
            ],
            "recusados": list(self.recusados),
            "sandbox": list(self.sandbox),
            "erros": list(self.erros),
            "steam_aberta": self.steam_aberta,
            "jogo_aberto": self.jogo_aberto,
        }


def caminho_do_registro(home: Path | None = None) -> Path:
    """`~/.local/state/hefesto-dualsense4unix/wrapper-visto.json` (XDG)."""
    base = home or Path.home()
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    state_home = Path(xdg) if xdg and home is None else base / ".local/state"
    return state_home / "hefesto-dualsense4unix" / REGISTRO_BASENAME


def ler_registro(path: Path | None = None, home: Path | None = None) -> dict[str, str]:
    """AppIDs já vistos com o wrapper → epoch da última vez. Nunca levanta.

    Registro ausente/corrompido = vazio, e vazio é o lado SEGURO: sem memória,
    toda ausência vira ``novo`` — o produto ainda repara, só não promete que
    "isto funcionava antes". Alegar regressão sem base seria pior que calar.
    """
    destino = path if path is not None else caminho_do_registro(home)
    try:
        dados = json.loads(destino.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict):
        return {}
    appids = dados.get("appids")
    if not isinstance(appids, dict):
        return {}
    return {
        str(k): str(v)
        for k, v in appids.items()
        if str(k).isdigit()
    }


def gravar_registro(
    appids: Sequence[str], path: Path | None = None, home: Path | None = None
) -> bool:
    """Anota que estes appids foram vistos COM o wrapper. Best-effort.

    Só ACRESCENTA: um appid some do registro apenas se o arquivo for apagado.
    Isso é deliberado — um jogo desinstalado e reinstalado depois continua
    sabendo que já teve o wrapper, e uma leitura de vdf que falhou no meio não
    apaga a memória de nada.

    Escrita atômica (tmp + replace) porque o censo pode rodar em paralelo com
    a GUI e com o doctor; meio arquivo lido viraria registro vazio.
    """
    destino = path if path is not None else caminho_do_registro(home)
    atual = ler_registro(destino)
    agora = str(int(time.time()))
    novo = dict(atual)
    for appid in appids:
        alvo = str(appid).strip()
        if alvo.isdigit():
            novo[alvo] = agora
    if novo == atual and destino.exists():
        return True
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + ".hefesto-tmp")
        tmp.write_text(
            json.dumps({"schema": 1, "appids": novo}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        tmp.replace(destino)
        return True
    except OSError:
        return False


def censo_do_wrapper(
    home: Path | None = None,
    vdfs: Sequence[Path] | None = None,
    *,
    registro: Path | None = None,
    recusados: Sequence[str] | None = None,
    anotar: bool = True,
) -> Censo:
    """Quem tem e quem não tem a chamada do wrapper. **Nunca escreve no vdf.**

    Read-only sobre o `localconfig.vdf`, portanto seguro **com a Steam
    aberta** — que é a condição em que ela está quando o problema aparece, e a
    razão de a detecção ser uma camada separada do reparo.

    `anotar=True` atualiza o registro com quem está com o wrapper AGORA; é o
    que dá memória à distinção regressão/novo. Passe `anotar=False` para uma
    consulta que não deixa rastro (o `--censo` do doctor não precisa dela).

    Guardas contra alarme falso — o instrumento aqui mente mais fácil que o
    produto, e um aviso "seu jogo vai quebrar" que não é verdade custa a
    confiança dela:

    - vdf ilegível ou não-UTF-8 vira ERRO por-vdf, não uma biblioteca inteira
      de "faltantes";
    - vdf que parseia para ZERO apps é tratado como erro, não como "nenhum
      jogo tem wrapper": é o retrato de uma leitura pega no meio de a Steam
      regravar o arquivo;
    - vdf de Flatpak/Snap é pulado inteiro (lá o wrapper do host é invisível,
      então "não tem wrapper" é o estado CERTO, não um defeito).
    """
    fora = list(recusados if recusados is not None else ler_jogos_sem_wrapper())
    fora_set = {str(a).strip() for a in fora}
    com_wrapper: list[str] = []
    faltantes: list[JogoSemWrapper] = []
    sandbox: list[str] = []
    erros: list[str] = []
    ja_visto = ler_registro(registro, home)

    alvos = list(vdfs) if vdfs is not None else discover_vdfs(home)
    for vdf in alvos:
        if is_sandboxed_layout(vdf):
            sandbox.append(str(vdf))
            continue
        try:
            texto = vdf.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            erros.append(f"{vdf}: {exc}")
            continue
        apps = read_apps_by_appid(texto)
        if not apps:
            erros.append(
                f"{vdf}: nenhum app no bloco `apps` — leitura provavelmente "
                "pega no meio de uma regravação da Steam; não vou concluir nada"
            )
            continue
        for appid, valor in sorted(apps.items()):
            if appid in fora_set:
                continue
            if valor is not None and WRAPPER_PREFIX in valor:
                com_wrapper.append(appid)
                continue
            if valor is not None and has_extended_ignore(valor):
                motivo = MOTIVO_ESTENDIDO
            elif appid in ja_visto:
                motivo = MOTIVO_REGRESSAO
            else:
                motivo = MOTIVO_NOVO
            faltantes.append(
                JogoSemWrapper(
                    appid=appid,
                    rotulo=rotulo_do_jogo(appid, home),
                    opcoes=valor,
                    motivo=motivo,
                    vdf=str(vdf),
                )
            )

    if anotar and com_wrapper:
        gravar_registro(com_wrapper, registro, home)

    return Censo(
        com_wrapper=com_wrapper,
        faltantes=faltantes,
        recusados=sorted(fora_set),
        sandbox=sandbox,
        erros=erros,
        steam_aberta=steam_running(),
        jogo_aberto=steam_game_running(),
    )


def frase_do_aviso(censo: Censo) -> str:
    """A frase que vai para a TELA (GUI e doctor). `""` = nada a dizer.

    Regra dela, 09/08: tudo tem que chegar na interface. E a frase precisa
    nomear o JOGO — "1 jogo com problema" é o tipo de aviso que não ajuda
    ninguém a agir.

    A regressão vem primeiro e sozinha quando existe: é a única categoria em
    que algo PAROU de funcionar, e é a que explica o sintoma confuso (controle
    vivo, perfil aceso, jogo cego). Jogo novo é rotina de biblioteca, não
    susto, e por isso ganha uma frase mais fria.
    """
    regressoes = censo.regressoes
    novos = censo.novos
    if regressoes:
        nomes = juntar_rotulos([j.rotulo for j in regressoes])
        plural = "jogos perderam" if len(regressoes) > 1 else "jogo perdeu"
        return (
            f"{len(regressoes)} {plural} as Opções de Inicialização do Hefesto "
            f"na Steam: {nomes}. Sem elas, no Bluetooth o jogo tende a não "
            "enxergar controle nenhum — mesmo com o controle vivo, a luz acesa "
            "e o perfil aplicado. " + _como_reparar(censo)
        )
    if novos:
        nomes = juntar_rotulos([j.rotulo for j in novos])
        plural = "jogos nunca receberam" if len(novos) > 1 else "jogo nunca recebeu"
        return (
            f"{len(novos)} {plural} as Opções de Inicialização do Hefesto na "
            f"Steam: {nomes}. " + _como_reparar(censo)
        )
    if censo.intocaveis:
        nomes = juntar_rotulos([j.rotulo for j in censo.intocaveis])
        return (
            f"Opções de Inicialização com a lista de IGNORE estendida à mão em "
            f"{nomes} — não vou tocar nelas (remover só o trecho do Hefesto "
            "deixaria um fragmento que impede o jogo de abrir). Reparo manual."
        )
    return ""


def _como_reparar(censo: Censo) -> str:
    """O rodapé da frase: o que fazer AGORA, dado o estado da Steam."""
    if censo.jogo_aberto:
        return (
            "Vou repor assim que o jogo e a Steam fecharem — não mexo agora "
            "porque fechar a Steam com um jogo aberto mata o jogo."
        )
    if censo.steam_aberta:
        return (
            "Preciso da Steam FECHADA para repor (ela regrava o arquivo ao "
            "sair e engoliria a correção). Feche a Steam e eu reponho."
        )
    return "Posso repor agora, preservando as opções que você já tinha na linha."


def reparar_ou_adiar(
    home: Path | None = None,
    vdfs: Sequence[Path] | None = None,
    *,
    registro: Path | None = None,
    dry_run: bool = False,
) -> tuple[str, Censo, dict[str, list[dict[str, str]]] | None]:
    """Repõe o wrapper onde ele falta, ou ADIA dizendo por quê.

    Retorna ``(status, censo, resultado_do_apply | None)``.

    A ordem dos portões é a mesma do `main` do `steam_launch_options`, e não é
    negociável: **jogo aberto antes de tudo** (fechar a Steam ali mataria o
    jogo e o progresso não salvo), depois Steam aberta (a edição seria
    engolida na saída dela), e só então a escrita.

    O que a escrita preserva, e por quê importa aqui mais que em qualquer
    outro lugar: o Pragmata precisa do wrapper **e** do `VKD3D_CONFIG` que
    cura o crash de 14/08. Repor o wrapper jogando fora a linha dela trocaria
    "o jogo não vê o controle" por "o jogo fecha sozinho", que não é conserto
    nenhum. Quem garante isso é o `migrate_value`, que PREPENDE.

    Os jogos com IGNORE estendido ficam de fora do reparo por construção (o
    `apply_wrapper_vdf_text` os pula) e são reportados no censo — mexer neles
    deixaria um fragmento-comando pendurado e o jogo nunca mais abriria.
    """
    censo = censo_do_wrapper(home, vdfs, registro=registro)
    if not censo.reparaveis:
        return REPARO_NADA, censo, None
    if censo.jogo_aberto:
        return REPARO_ADIADO_JOGO, censo, None
    if censo.steam_aberta:
        return REPARO_ADIADO_STEAM, censo, None
    resultado = apply_wrapper_to_all_games(
        home=home,
        vdfs=list(vdfs) if vdfs is not None else None,
        dry_run=dry_run,
        excluir=censo.recusados,
    )
    if resultado["errors"]:
        return REPARO_ERRO, censo, resultado
    if not dry_run and resultado["applied"]:
        gravar_registro(
            [item["appid"] for item in resultado["applied"]], registro, home
        )
    return REPARO_FEITO, censo, resultado


# --------------------------------------------------------------------------
# CLI — o doctor.sh consome `--censo` (JSON); `--relatorio` é para gente.
# --------------------------------------------------------------------------


def _imprimir_relatorio(censo: Censo) -> int:
    print(f"[sentinela-wrapper] jogos COM o wrapper: {len(censo.com_wrapper)}")
    for vdf in censo.sandbox:
        print(f"[sentinela-wrapper] vdf sandbox (pulado): {vdf}")
    for erro in censo.erros:
        print(f"[sentinela-wrapper] ERRO: {erro}")
    if censo.recusados:
        print(
            "[sentinela-wrapper] fora por escolha dela: "
            + ", ".join(censo.recusados)
        )
    for jogo in censo.faltantes:
        print(
            f"[sentinela-wrapper] SEM wrapper ({jogo.motivo}): {jogo.rotulo}"
            + (f"  →  {jogo.opcoes}" if jogo.opcoes else "  →  (sem a linha)")
        )
    aviso = frase_do_aviso(censo)
    if aviso:
        print(f"[sentinela-wrapper] {aviso}")
    else:
        print("[sentinela-wrapper] nada a avisar: todo jogo elegível tem o wrapper")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sentinela_do_wrapper",
        description=(
            "Detecta jogos da Steam que perderam a chamada do wrapper "
            "hefesto-launch, avisa e (com a Steam fechada) repõe preservando "
            "as opções existentes. Sem argumentos, --relatorio."
        ),
    )
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument(
        "--relatorio", action="store_true", help="relatório legível (default)"
    )
    grupo.add_argument("--censo", action="store_true", help="o censo em JSON")
    grupo.add_argument(
        "--reparar",
        action="store_true",
        help="repõe o wrapper onde falta (exige Steam fechada; adia se não der)",
    )
    grupo.add_argument(
        "--nao-quero",
        metavar="APPID",
        help="marca um jogo como 'sem wrapper, de propósito'",
    )
    grupo.add_argument(
        "--quero", metavar="APPID", help="desfaz o --nao-quero de um jogo"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="não escreve nada (com --reparar)"
    )
    parser.add_argument(
        "--vdf",
        action="append",
        type=Path,
        default=None,
        metavar="ARQUIVO",
        help="localconfig.vdf explícito (repetível; default: descoberta automática)",
    )
    args = parser.parse_args(argv)

    if args.nao_quero or args.quero:
        # Import tardio pelo mesmo motivo do topo: modo avulso sem o pacote.
        try:
            from .steam_launch_options import (
                desmarcar_jogo_sem_wrapper,
                marcar_jogo_sem_wrapper,
            )
        except ImportError:  # pragma: no cover - script avulso
            from steam_launch_options import (  # type: ignore[no-redef]
                desmarcar_jogo_sem_wrapper,
                marcar_jogo_sem_wrapper,
            )
        if args.nao_quero:
            status = marcar_jogo_sem_wrapper(args.nao_quero, nota="pedido na CLI")
        else:
            status = desmarcar_jogo_sem_wrapper(args.quero)
        print(f"[sentinela-wrapper] {status}")
        return 0 if status in ("adicionado", "removido", "ja_estava", "nao_estava") else 1

    if args.censo:
        censo = censo_do_wrapper(vdfs=args.vdf, anotar=False)
        print(json.dumps(censo.como_dicionario(), ensure_ascii=False))
        return 0

    if args.reparar:
        status, censo, _ = reparar_ou_adiar(vdfs=args.vdf, dry_run=args.dry_run)
        _imprimir_relatorio(censo)
        print(f"[sentinela-wrapper] reparo: {status}")
        # 3 = adiado (nada foi tocado), igual ao rc de recusa do vizinho.
        if status in (REPARO_ADIADO_JOGO, REPARO_ADIADO_STEAM):
            return 3
        return 1 if status == REPARO_ERRO else 0

    return _imprimir_relatorio(censo_do_wrapper(vdfs=args.vdf))


if __name__ == "__main__":  # pragma: no cover - entrypoint do doctor
    sys.exit(main())
