"""PRONTUARIO-01 — o que o DISCO sabe sobre cada jogo, e o que ele NÃO sabe.

O alvo que ela nomeou em 15/08/2026, ao sair: *"espero de fato que tenhamos
tudo resolvido e cada um dos jogos locais jogável via cabo ou bt"*. Este módulo
é a régua desse alvo — e a primeira coisa que ele faz é recusar o número fácil.

O QUE ELE NUNCA DIZ
-------------------
**"Este jogo funciona."** O disco não sabe disso, e fingir que sabe seria
repetir o defeito mais caro daqui. Medido em 16/08/2026: `Duskfade` e
`DON'T SCREAM` têm a MESMA assinatura no disco — mesmo motor, mesmas famílias
de API (`rawinput`, `xinput` por `LoadLibrary`), mesmo wrapper na linha, mesmo
Steam Input desligado — e um funciona e o outro não. Qualquer prontuário que
pintasse os dois de verde estaria certo sobre um e errado sobre o outro, sem
maneira de saber qual.

Por isso o veredito é **impedimento**, não aprovação:

- ``IMPEDIDO`` — há um estorvo NOMEADO, com a cura ao lado;
- ``SEM_IMPEDIMENTO_CONHECIDO`` — nada que este módulo saiba detectar. Não é
  promessa de que vai funcionar; é a ausência de motivo conhecido para não;
- ``NAO_SEI`` — o disco não deixou ler (pasta ausente, executável ilegível).

É a mesma disciplina do `WRAPPER-EM-TODOS-01`, o portão que passou a noite
verde com o Pragmata quebrado por contar jogos em vez de nomear o que faltava:
**um censo que só conta mente na direção mais cara, a de parecer completo.**

O QUE ELE DIZ, E ISSO É NOVO
-----------------------------
O cruzamento que faltava. Cada peça já existia sozinha — a linha de
inicialização (`sentinela_do_wrapper`), a API de entrada do executável
(`api_de_entrada`), o Steam Input e a allowlist (`steam_launch_options`) — e
ninguém as tinha posto lado a lado por jogo. Posto lado a lado, o censo da
máquina dela (24 jogos instalados, 16/08/2026) mostra o número que decide o
alvo dela:

    entende_dualsense   7 jogos   SDL ou o plugin DualShock no binário
    indeciso           15 jogos   XInput e mais nada — o vpad só chega por espelho
    sem_evidencia       2 jogos   nenhuma agulha, ou executável ilegível

Quinze dos vinte e quatro dependem de que alguém faça o espelho XInput do nosso
vpad `054c:0df2`. Isso não é detalhe de um jogo: é a maioria da biblioteca.

100% stdlib e read-only, como os vizinhos — o `doctor.sh` o roda com o
`python3` do sistema, sem venv, e ele não escreve em lugar nenhum.
"""
from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

try:  # importado como módulo do pacote (GUI/daemon/testes)
    from .api_de_entrada import Evidencia, Veredito, examinar_pasta
    from .steam_launch_options import (
        _PAR_ACF,
        WRAPPER_PREFIX,
        _desescapar_acf,
        discover_vdfs,
        has_extended_ignore,
        is_sandboxed_layout,
        parse_steam_input_allowlist,
        pastas_steamapps,
        read_apps_by_appid,
        steam_input_allowlist_path,
    )
except ImportError:  # pragma: no cover - executado como script avulso
    from api_de_entrada import Evidencia, Veredito, examinar_pasta  # type: ignore[no-redef]
    from steam_launch_options import (  # type: ignore[no-redef]
        _PAR_ACF,
        WRAPPER_PREFIX,
        _desescapar_acf,
        discover_vdfs,
        has_extended_ignore,
        is_sandboxed_layout,
        parse_steam_input_allowlist,
        pastas_steamapps,
        read_apps_by_appid,
        steam_input_allowlist_path,
    )

#: Os três vereditos. Ver o cabeçalho: nenhum deles é "funciona".
IMPEDIDO = "impedido"
SEM_IMPEDIMENTO = "sem_impedimento_conhecido"
NAO_SEI = "nao_sei"

#: Os estorvos que o disco consegue NOMEAR. Cada um traz a cura junto — um
#: diagnóstico sem cura ao lado só transfere o trabalho para ela.
SEM_WRAPPER = "sem_wrapper"
LINHA_INTOCAVEL = "linha_intocavel"
SEM_EXECUTAVEL = "sem_executavel"
EXCECAO_INERTE = "excecao_inerte"

#: Texto de cada estorvo: (o que é, a cura, a cura é automática?).
_ESTORVOS: dict[str, tuple[str, str, bool]] = {
    SEM_WRAPPER: (
        "A linha de Opções de Inicialização não chama o hefesto-launch, "
        "então o jogo nunca lê a máscara e vale a lista da Steam — que manda "
        "ignorar o nosso controle virtual.",
        "O Hefesto repõe sozinho: ao salvar ou aplicar um perfil, e também "
        "assim que a Steam fechar (é o único instante em que a reposição "
        "sobrevive — com ela viva, regrava o arquivo ao sair e engole).",
        True,
    ),
    LINHA_INTOCAVEL: (
        "A linha tem uma lista de dispositivos ignorados estendida à mão. "
        "Repor o wrapper por cima quebraria o que está lá.",
        "Só reparo manual: revise a linha na Steam antes de deixar o Hefesto "
        "cuidar dela.",
        False,
    ),
    SEM_EXECUTAVEL: (
        "Não foi possível ler nenhum executável na pasta do jogo, então não dá "
        "para saber que API de entrada ele usa.",
        "Nenhuma — é cegueira do instrumento, não defeito do jogo.",
        False,
    ),
    EXCECAO_INERTE: (
        "Este jogo está na sua lista de exceções do Steam Input, mas o Steam "
        "Input está DESLIGADO para ele. A lista só preserva o que já estava "
        "ligado — ela nunca liga.",
        "Ligue o Steam Input para este jogo na própria Steam (Propriedades > "
        "Controle). A exceção então passa a valer e o Hefesto não o desliga de "
        "novo.",
        False,
    ),
}

#: `UseSteamControllerConfig`: o bloco do jogo dentro de `apps`. `"0"` é
#: desligado; qualquer outro valor é alguma forma de ligado.
_USA_STEAM_INPUT = "usesteamcontrollerconfig"
#: A chave global equivalente, em `system`.
_PS_SUPPORT_GLOBAL = "steamcontroller_pssupport"

_SO_CHAVE_RE = re.compile(r'^\s*"([^"]+)"\s*$')

#: Ferramentas que a Steam instala como se fossem jogos.
_INFRAESTRUTURA_RE = re.compile(
    r"^(proton\b|steam linux runtime|steamworks common|steam controller configs)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Estorvo:
    """Um impedimento nomeado, e o que fazer com ele."""

    chave: str

    @property
    def o_que(self) -> str:
        return _ESTORVOS[self.chave][0]

    @property
    def a_cura(self) -> str:
        return _ESTORVOS[self.chave][1]

    @property
    def automatica(self) -> bool:
        """O produto conserta sozinho, sem ela clicar em nada?"""
        return _ESTORVOS[self.chave][2]


@dataclass(frozen=True)
class Prontuario:
    """A ficha de UM jogo: fatos lidos do disco, e o veredito por último."""

    appid: str
    nome: str
    #: Pasta de instalação. `None` = o manifesto não diz, ou sumiu do disco.
    raiz: Path | None = None
    #: A `LaunchOptions` crua. `None` = o jogo nem tem a linha.
    linha: str | None = None
    #: O que o executável revelou. `None` = não foi examinado (pasta ausente).
    evidencia: Evidencia | None = None
    #: `UseSteamControllerConfig` do bloco do jogo. `None` = herda o global.
    steam_input: str | None = None
    #: O global `SteamController_PSSupport`, para quando o jogo não tem o seu.
    steam_input_global: str | None = None
    #: Está no `steam_input_apps.txt` (o opt-in dela)?
    na_allowlist: bool = False

    # -- os fatos derivados, cada um com um nome que diz o que ele é --------

    @property
    def tem_wrapper(self) -> bool:
        return bool(self.linha) and WRAPPER_PREFIX in (self.linha or "")

    @property
    def linha_intocavel(self) -> bool:
        return has_extended_ignore(self.linha or "")

    @property
    def steam_input_ligado(self) -> bool | None:
        """True/False, ou `None` quando nem o jogo nem o global se pronunciam."""
        valor = self.steam_input if self.steam_input is not None else self.steam_input_global
        if valor is None:
            return None
        return valor.strip() != "0"

    @property
    def api(self) -> Veredito:
        return self.evidencia.veredito if self.evidencia else Veredito.SEM_EVIDENCIA

    @property
    def depende_de_espelho(self) -> bool:
        """O vpad só chega a este jogo por um espelho XInput?

        Verdadeiro para o balde `indeciso`: XInput no binário e nenhum sinal de
        SDL nem do plugin DualShock. **Não é sentença de que vai falhar** — o
        `xinput1_4` do Wine espelha o que o DInput enxerga, e DON'T SCREAM cai
        aqui e funciona. É o aviso de que este jogo depende de uma ponte que o
        Hefesto não controla sozinho.
        """
        return self.api is Veredito.INDECISO

    @property
    def estorvos(self) -> list[Estorvo]:
        """Tudo que o disco consegue nomear como impedimento, em ordem de peso."""
        achados: list[Estorvo] = []
        if not self.tem_wrapper:
            achados.append(Estorvo(LINHA_INTOCAVEL if self.linha_intocavel else SEM_WRAPPER))
        if self.na_allowlist and self.steam_input_ligado is False:
            # Ela pôs o jogo na lista de exceções — o gesto diz "quero Steam
            # Input aqui". Achado em 16/08/2026: o Sackboy estava assim, e a
            # exceção não fazia nada. Nomear é o mínimo; DECIDIR é dela, porque
            # daqui não dá para distinguir "a lista entrou tarde" de "eu desliguei
            # depois e mudei de ideia".
            achados.append(Estorvo(EXCECAO_INERTE))
        if self.raiz is not None and (self.evidencia is None or not self.evidencia.executavel):
            achados.append(Estorvo(SEM_EXECUTAVEL))
        return achados

    @property
    def veredito(self) -> str:
        if self.estorvos:
            return IMPEDIDO
        if self.raiz is None or self.evidencia is None:
            return NAO_SEI
        return SEM_IMPEDIMENTO

    def como_dicionario(self) -> dict[str, object]:
        """Forma JSON — o que a GUI e o `doctor.sh` consomem."""
        return {
            "appid": self.appid,
            "nome": self.nome,
            "veredito": self.veredito,
            "tem_wrapper": self.tem_wrapper,
            "api": self.api.value,
            "depende_de_espelho": self.depende_de_espelho,
            "steam_input_ligado": self.steam_input_ligado,
            "na_allowlist": self.na_allowlist,
            "estorvos": [
                # A chave abaixo é JSON, não prosa: o `doctor.sh` a lê com
                # `jq`, e chave acentuada em shell é o tipo de detalhe que
                # quebra num terminal e não no outro. O texto que ELA lê está
                # em `_ESTORVOS`, acentuado.
                {"chave": e.chave, "o_que": e.o_que, "cura": e.a_cura,
                 "automatica": e.automatica}  # (noqa-acento): chave de JSON
                for e in self.estorvos
            ],
        }


@dataclass(frozen=True)
class Censo:
    """Os prontuários de todos os jogos instalados, e o que o conjunto diz."""

    jogos: list[Prontuario] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

    @property
    def impedidos(self) -> list[Prontuario]:
        return [j for j in self.jogos if j.veredito == IMPEDIDO]

    @property
    def curaveis_sozinho(self) -> list[Prontuario]:
        """Impedidos cuja cura o produto aplica sem ela clicar em nada."""
        return [j for j in self.impedidos if all(e.automatica for e in j.estorvos)]

    @property
    def dependem_de_espelho(self) -> list[Prontuario]:
        return [j for j in self.jogos if j.depende_de_espelho]

    def por_api(self) -> dict[str, list[Prontuario]]:
        saida: dict[str, list[Prontuario]] = {v.value: [] for v in Veredito}
        for jogo in self.jogos:
            saida[jogo.api.value].append(jogo)
        return saida

    def frase(self) -> str:
        """Uma linha para a tela. Nomeia, nunca só conta.

        A regra do `WRAPPER-EM-TODOS-01` aplicada à frase: se há jogo impedido,
        o nome dele aparece — "3 jogos com pendência" é exatamente o texto que
        deixou o Pragmata quebrado a noite inteira.
        """
        if not self.jogos:
            return "Nenhum jogo da Steam instalado por aqui."
        impedidos = self.impedidos
        if not impedidos:
            return (
                f"{len(self.jogos)} jogos, nenhum com pendência conhecida "
                f"({len(self.dependem_de_espelho)} dependem do espelho XInput)."
            )
        nomes = ", ".join(j.nome for j in impedidos[:3])
        resto = f" e mais {len(impedidos) - 3}" if len(impedidos) > 3 else ""
        automaticos = len(self.curaveis_sozinho)
        cauda = (
            f" O Hefesto repõe {automaticos} ao salvar um perfil."
            if automaticos
            else " Nenhuma se conserta sozinha — veja o detalhe de cada uma."
        )
        return f"Com pendência: {nomes}{resto}.{cauda}"

    def como_dicionario(self) -> dict[str, object]:
        return {
            "jogos": [j.como_dicionario() for j in self.jogos],
            "erros": list(self.erros),
            "resumo": {
                "total": len(self.jogos),
                "impedidos": len(self.impedidos),
                "curaveis_sozinho": len(self.curaveis_sozinho),
                "dependem_de_espelho": len(self.dependem_de_espelho),
                "por_api": {k: len(v) for k, v in self.por_api().items()},
            },
        }


def e_infraestrutura(nome: str) -> bool:
    """O `.acf` é ferramenta da Steam (Proton, runtime, redistribuíveis)?

    Gêmeo do `jogos_locais.e_ferramenta_da_steam`, repetido aqui porque aquele
    módulo importa `dataclasses` e `unicodedata` de que este não precisa, e a
    promessa de rodar como script solto no `python3` do sistema vale mais que
    poupar oito linhas.
    """
    return _INFRAESTRUTURA_RE.match(nome.strip()) is not None


def _campos_do_manifesto(texto: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for linha in texto.splitlines():
        par = _PAR_ACF.match(linha)
        if par is not None:
            campos.setdefault(
                _desescapar_acf(par.group("chave")).lower(),
                _desescapar_acf(par.group("valor")),
            )
    return campos


def jogos_instalados(home: Path | None = None) -> list[tuple[str, str, Path | None]]:
    """`[(appid, nome, raiz)]` dos jogos com `appmanifest` em disco.

    Infraestrutura fora. `raiz` é `None` quando o manifesto existe mas a pasta
    não — a Steam deixa manifesto para trás em desinstalação interrompida, e um
    prontuário que sumisse com o jogo esconderia justamente esse estado.
    """
    achados: dict[str, tuple[str, str, Path | None]] = {}
    for pasta in pastas_steamapps(home):
        try:
            manifestos = sorted(pasta.glob("appmanifest_*.acf"))
        except OSError:  # pragma: no cover - pasta sumiu entre o listar e o ler
            continue
        for acf in manifestos:
            try:
                campos = _campos_do_manifesto(acf.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            appid = campos.get("appid", "").strip()
            nome = campos.get("name", "").strip()
            if not appid or not nome or e_infraestrutura(nome):
                continue
            instalada = campos.get("installdir", "").strip()
            raiz = pasta / "common" / instalada if instalada else None
            if raiz is not None and not raiz.is_dir():
                raiz = None
            achados.setdefault(appid, (appid, nome, raiz))
    return sorted(achados.values(), key=lambda t: t[1].lower())


def _steam_input_do_vdf(texto: str) -> tuple[dict[str, str], str | None]:
    """`({appid: UseSteamControllerConfig}, SteamController_PSSupport global)`.

    Parser estrutural pela mesma razão do `read_apps_by_appid`: um regex de
    linha solta enxerga o valor sem saber de qual jogo ele é, e o
    `UseSteamControllerConfig` aparece dentro do bloco de cada app.
    """
    por_app: dict[str, str] = {}
    global_ps: str | None = None
    pilha: list[str] = []
    pendente: str | None = None
    for cru in texto.splitlines():
        linha = cru.strip()
        if not linha:
            continue
        if linha == "{":
            pilha.append(pendente if pendente is not None else "")
            pendente = None
            continue
        if linha == "}":
            if pilha:
                pilha.pop()
            pendente = None
            continue
        par = _PAR_ACF.match(cru)
        if par is not None:
            pendente = None
            chave = _desescapar_acf(par.group("chave")).lower()
            valor = _desescapar_acf(par.group("valor"))
            if chave == _PS_SUPPORT_GLOBAL:
                global_ps = valor
            elif (
                chave == _USA_STEAM_INPUT
                and len(pilha) >= 2
                and pilha[-2].lower() == "apps"
                and pilha[-1].isdigit()
            ):
                por_app[pilha[-1]] = valor
            continue
        so_chave = _SO_CHAVE_RE.match(cru)
        if so_chave is not None:
            pendente = _desescapar_acf(so_chave.group(1))
    return por_app, global_ps


def levantar_censo(
    home: Path | None = None,
    *,
    allowlist: Sequence[str] | None = None,
    examinar: bool = True,
) -> Censo:
    """A fotografia read-only de toda a biblioteca instalada.

    `examinar=False` pula a varredura dos executáveis — que é a parte cara
    (segundos, num jogo grande). A GUI a quer; um portão que só confere o
    wrapper, não.
    """
    linhas: dict[str, str | None] = {}
    steam_input: dict[str, str] = {}
    global_ps: str | None = None
    erros: list[str] = []
    for vdf in discover_vdfs(home):
        if is_sandboxed_layout(vdf):
            continue
        try:
            texto = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            erros.append(f"{vdf}: {exc}")
            continue
        for appid, valor in read_apps_by_appid(texto).items():
            linhas.setdefault(appid, valor)
        do_vdf, ps = _steam_input_do_vdf(texto)
        for appid, valor in do_vdf.items():
            steam_input.setdefault(appid, valor)
        if global_ps is None:
            global_ps = ps

    if allowlist is None:
        try:
            allowlist = parse_steam_input_allowlist(
                steam_input_allowlist_path().read_text(encoding="utf-8")
            )
        except OSError:
            allowlist = []
    permitidos = {str(a).strip() for a in allowlist}

    fichas: list[Prontuario] = []
    for appid, nome, raiz in jogos_instalados(home):
        evidencia: Evidencia | None = None
        if raiz is not None and examinar:
            try:
                evidencia = examinar_pasta(raiz)
            except OSError as exc:  # pragma: no cover - permissão no meio da varredura
                erros.append(f"{nome}: {exc}")
        fichas.append(
            Prontuario(
                appid=appid,
                nome=nome,
                raiz=raiz,
                linha=linhas.get(appid),
                evidencia=evidencia,
                steam_input=steam_input.get(appid),
                steam_input_global=global_ps,
                na_allowlist=appid in permitidos,
            )
        )
    return Censo(jogos=fichas, erros=erros)


def _tabela(censo: Censo) -> str:
    """O relatório de terminal — uma linha por jogo, e o nome sempre."""
    largura = max((len(j.nome) for j in censo.jogos), default=4)
    largura = min(largura, 34)
    linhas = [
        f"{'jogo':{largura}} | {'veredito':26} | {'api':18} | wrapper | Steam Input",
        "-" * (largura + 70),
    ]
    for jogo in censo.jogos:
        si = jogo.steam_input_ligado
        texto_si = "herdado" if si is None else ("ligado" if si else "desligado")
        if jogo.na_allowlist:
            texto_si += " (allowlist)"
        linhas.append(
            f"{jogo.nome[:largura]:{largura}} | {jogo.veredito:26} | "
            f"{jogo.api.value:18} | {'sim' if jogo.tem_wrapper else 'NÃO':7} | {texto_si}"
        )
    for jogo in censo.impedidos:
        linhas.append("")
        linhas.append(f"  {jogo.nome}:")
        for estorvo in jogo.estorvos:
            marca = "o Hefesto repõe sozinho" if estorvo.automatica else "só reparo manual"
            linhas.append(f"    - {estorvo.o_que}")
            linhas.append(f"      cura: {estorvo.a_cura} ({marca})")
    linhas.append("")
    linhas.append(censo.frase())
    return "\n".join(linhas)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="a forma que a GUI consome")
    ap.add_argument(
        "--rapido",
        action="store_true",
        help="não varre os executáveis (só a linha de inicialização)",
    )
    args = ap.parse_args(list(argv) if argv is not None else None)
    censo = levantar_censo(examinar=not args.rapido)
    if args.json:
        print(json.dumps(censo.como_dicionario(), ensure_ascii=False, indent=2))
    else:
        print(_tabela(censo))
    return 1 if censo.impedidos else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
