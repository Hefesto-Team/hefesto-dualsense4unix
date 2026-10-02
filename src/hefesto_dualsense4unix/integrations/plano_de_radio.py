"""plano_de_radio.py — a conta de fatias POR ADAPTADOR, com nome de jogador."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.integrations.conexao_zumbi import mac_limpo
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    N_MAX_PONTES,
    SEM_ADAPTADOR,
    SLOTS_POR_RELATORIO,
    SLOTS_POR_SEGUNDO,
    Ocupacao,
    OrcamentoDoAdaptador,
    adaptador_por_uniq,
    orcamento_por_adaptador,
    palavra_da_ocupacao,
    palavra_das_pontes,
)

ENSAIO_MAXIMO_DESTA_CASA = 2

MESA_CHEIA_DESTA_CASA = 4

SEM_NUMERO = "Sem número ainda"

ADAPTADOR_SEM_NOME = "Adaptador sem nome"

ADAPTADOR_DESCONHECIDO = "Adaptador que não sei qual é"


@dataclass(frozen=True)
class PlanoDoAdaptador:
    """O que está num adaptador, o que custa agora, e o que custaria declarado.

    ``endereco`` é o BD Address minúsculo do adaptador como o ``HID_PHYS`` do
    uevent o publica, ou :data:`radio_da_mesa.SEM_ADAPTADOR` (string vazia)
    para o balde do "não sei de quem é".

    ``jogadores`` traz o ``player_slot`` de cada controle NA ORDEM em que
    chegaram, com ``None`` para quem ainda não tem número — nunca chutado por
    posição. A conta ``índice + 1`` já deu "Jogador 4" a dois cards da mesma
    mesa (22/08/2026), e null honesto vale mais que número errado.
    """

    endereco: str
    apelido: str = ""
    jogadores: tuple[int | None, ...] = ()
    com_mic_de_pe: frozenset[str] = field(default_factory=frozenset)
    com_mic_declarado: frozenset[str] = field(default_factory=frozenset)
    agora: Ocupacao = field(default_factory=Ocupacao)
    planejada: Ocupacao = field(default_factory=Ocupacao)
    orcamento: OrcamentoDoAdaptador | None = None

    @property
    def pontes(self) -> int:
        """Quantas pontes de som e vibração estão de pé neste adaptador."""
        return len(self.orcamento.pontes) if self.orcamento is not None else 0

    @property
    def n_max(self) -> int:
        """Quantas pontes o adaptador comporta — o do dono, nunca um digitado."""
        return self.orcamento.n_max if self.orcamento is not None else N_MAX_PONTES

    @property
    def vaga_de_ponte(self) -> int:
        """Quantas pontes ainda cabem aqui. Negativo quando já passou do limite."""
        return self.n_max - self.pontes

    @property
    def no_ar(self) -> int:
        """Quantos controles estão no rádio deste adaptador."""
        if self.orcamento is not None:
            return len(self.orcamento.controles)
        return self.agora.controles

    @property
    def rotulo_das_pontes(self) -> str:
        """Folgada, Apertada ou Cheia — pelas pontes, pela palavra do dono."""
        return palavra_das_pontes(self.pontes, self.n_max)

    @property
    def nome_na_tela(self) -> str:
        """O nome DELA, nunca ``hciN`` — ver :data:`ADAPTADOR_SEM_NOME`."""
        if self.apelido:
            return self.apelido
        if not self.endereco:
            return ADAPTADOR_DESCONHECIDO
        return ADAPTADOR_SEM_NOME

    @property
    def declarado_que_nao_subiu(self) -> frozenset[str]:
        """Os ``uniq`` que ela marcou e cuja ponte não está de pé."""
        return frozenset(self.com_mic_declarado - self.com_mic_de_pe)


@dataclass(frozen=True)
class Redistribuicao:
    """A ordem de serviço, como DADO PURO — sem uma linha de ``gi``."""

    origem: str
    destino: str
    origem_na_tela: str
    destino_na_tela: str
    o_que_eu_vi: str
    por_que_importa: str
    ganho_esperado: str
    controle: str
    modo: str
    pontes_na_origem_depois: int
    pontes_no_destino_depois: int
    n_max: int

    def publicar(self) -> dict[str, Any]:
        """O que viaja no ``state_full`` — só tipos de JSON."""
        return {
            "origem": self.origem,
            "destino": self.destino,
            "controle": self.controle,
            "modo": self.modo,
            "pontes_na_origem_depois": self.pontes_na_origem_depois,
            "pontes_no_destino_depois": self.pontes_no_destino_depois,
            "n_max": self.n_max,
        }


POR_QUE_IMPORTA_O_NUMERO = (
    "os controles de um adaptador dividem o que ele manda por segundo: com menos "
    "controles no mesmo adaptador, cada um manda mais movimento."
)

DIFERENCA_QUE_EQUILIBRA = 2

FRASE_DO_ADAPTADOR_UNICO = (
    "Todos os controles estão no mesmo adaptador, e é o único que você tem. "
    "Um segundo adaptador dividiria a fila."
)

POR_QUE_IMPORTA = (
    "cada ponte de som ou vibração ocupa o rádio sem parar, e acima do limite "
    "o adaptador não comporta todas."
)


def _numero(valor: float) -> str:
    """Uma casa decimal, com vírgula — é assim que ela lê número nesta casa."""
    return formata_pt_br(valor)


def _hex(valor: str) -> str:
    """Só os dígitos hex minúsculos — o mesmo normalizador do ``radio_da_mesa``."""
    return norm_mac(valor) or ""


def _somar(
    base: Ocupacao, *, com_mic: bool = False, quantos: int = 1
) -> Ocupacao:
    """``base`` mais ``quantos`` controles — a ÚNICA aritmética deste módulo."""
    if quantos <= 0:
        return base
    if com_mic:
        entrada = HZ_INPUT_COM_MIC * SLOTS_POR_RELATORIO * quantos
        audio = HZ_AUDIO_COM_MIC * SLOTS_POR_RELATORIO * quantos
    else:
        entrada = HZ_INPUT_SEM_MIC * SLOTS_POR_RELATORIO * quantos
        audio = 0.0
    return Ocupacao(
        slots_input=base.slots_input + entrada,
        slots_audio=base.slots_audio + audio,
        slots_teto=base.slots_teto,
        controles=base.controles + quantos,
        com_microfone=base.com_microfone + (quantos if com_mic else 0),
    )


def apelido_por_endereco(dongles: Sequence[Any]) -> dict[str, str]:
    """``endereço minúsculo -> nome DELA``, só para quem tem nome."""
    achados: dict[str, str] = {}
    for dongle in dongles:
        endereco = str(getattr(dongle, "endereco", "") or "").lower()
        nome = str(getattr(dongle, "nome", "") or "")
        if endereco and nome:
            achados[endereco] = nome
    return achados


def plano_por_adaptador(
    controles: Iterable[Mapping[str, Any]],
    *,
    com_ponte_de_mic: Iterable[str] = (),
    mic_declarado: Iterable[str] = (),
    apelidos: Mapping[str, str] | None = None,
    ar: Mapping[str, Any] | None = None,
    n_max: int = N_MAX_PONTES,
    adaptadores: Iterable[str] = (),
    raiz: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> dict[str, PlanoDoAdaptador]:
    """``{endereço: PlanoDoAdaptador}`` a partir do estado do daemon.

    ``controles`` é ``state["controllers"]`` como já chega. ``com_ponte_de_mic``
    é ``bt_mic.uniqs`` — a ponte que SUBIU; ``mic_declarado`` são as chaves de
    ``maquina.json`` que ELA marcou. As duas alimentam contas diferentes, e é
    a regra 1 do cabeçalho.

    As três regras de descarte são as mesmas de
    ``radio_da_mesa.ocupacao_por_adaptador``, e por isso não se reescrevem: quem
    não está em ``bt`` não toca o rádio, quem não tem endereço legível vai para
    o balde do "não sei", e a fração passa de 1,0 quando passa.

    DESDE 23/09/2026 (MOVER-UM-POR-VEZ-01) cada plano leva o
    ``OrcamentoDoAdaptador`` do dono — ``ar`` e ``n_max`` vão direto para
    ``radio_da_mesa.orcamento_por_adaptador``. E o adaptador VAZIO passa a
    existir: todo endereço que o ``ar`` mede ou que vem em ``adaptadores`` (o
    que o BlueZ conhece) ganha plano, com zero controles. Era o ACHADO 2 da
    medição das duas réguas (``test_as_duas_reguas_do_arranjo_divergem_onde``):
    o dongle livre não existia para a régua, e ela mandava a frase do adaptador
    único com um adaptador vazio na mesa.

    O ``adaptador`` que o daemon já publica por controle (``_merge_radio``, do
    ``HID_PHYS``) vale sem reler o sysfs; só quem chega sem ele é resolvido aqui
    — a mesma regra do ``orcamento_por_adaptador``, e é ela que deixa esta conta
    rodar no tique do ``state_full`` sem varrer ``/sys`` a cada volta.
    """
    conectados = [
        controle
        for controle in controles
        if controle.get("transport") == "bt" and controle.get("connected", True)
    ]
    conhecidos = {_mac_minusculo(e) for e in adaptadores} - {""}
    if not conectados and not conhecidos and not ar:
        return {}

    uniqs = [_hex(str(c.get("uniq") or "")) for c in conectados]
    publicados = {
        uniq: _mac_minusculo(str(c.get("adaptador") or ""))
        for c, uniq in zip(conectados, uniqs, strict=True)
        if uniq and _mac_minusculo(str(c.get("adaptador") or ""))
    }
    faltam = [u for u in uniqs if u and u not in publicados]
    enderecos = dict(publicados)
    if faltam:
        enderecos.update(adaptador_por_uniq(faltam, raiz=raiz, listar=listar, ler=ler))
    de_pe = {_hex(u) for u in com_ponte_de_mic if _hex(u)}
    declarados = {_hex(u) for u in mic_declarado if _hex(u)}
    nomes = {k.lower(): v for k, v in (apelidos or {}).items()}
    orcamentos = orcamento_por_adaptador(
        conectados, ar=ar, n_max=n_max, raiz=raiz, listar=listar, ler=ler
    )

    juntos: dict[str, dict[str, Any]] = {}

    def _vazio() -> dict[str, Any]:
        return {
            "jogadores": [],
            "de_pe": set(),
            "declarados": set(),
            "agora": Ocupacao(),
            "planejada": Ocupacao(),
        }

    for endereco in sorted(conhecidos | {e for e in orcamentos if e}):
        juntos.setdefault(endereco, _vazio())
    for controle, uniq in zip(conectados, uniqs, strict=True):
        endereco = enderecos.get(uniq, SEM_ADAPTADOR) if uniq else SEM_ADAPTADOR
        alvo = juntos.setdefault(endereco, _vazio())
        alvo["jogadores"].append(_inteiro(controle.get("player_slot")))
        com_mic_agora = bool(uniq) and uniq in de_pe
        com_mic_plano = bool(uniq) and uniq in declarados
        if com_mic_agora:
            alvo["de_pe"].add(uniq)
        if com_mic_plano:
            alvo["declarados"].add(uniq)
        alvo["agora"] = _somar(alvo["agora"], com_mic=com_mic_agora)
        alvo["planejada"] = _somar(alvo["planejada"], com_mic=com_mic_plano)

    return {
        endereco: PlanoDoAdaptador(
            endereco=endereco,
            apelido=nomes.get(endereco, ""),
            jogadores=tuple(dados["jogadores"]),
            com_mic_de_pe=frozenset(dados["de_pe"]),
            com_mic_declarado=frozenset(dados["declarados"]),
            agora=dados["agora"],
            planejada=dados["planejada"],
            orcamento=orcamentos.get(endereco)
            or OrcamentoDoAdaptador(adaptador=endereco, n_max=n_max),
        )
        for endereco, dados in juntos.items()
    }


def _mac_minusculo(valor: str) -> str:
    """``aa:bb:…`` minúsculo, ou ``""`` — pela régua ESTRITA de ``conexao_zumbi``."""
    texto = str(valor or "").strip().lower()
    if len(texto) == 12 and all(c in "0123456789abcdef" for c in texto):
        texto = ":".join(texto[i:i + 2] for i in range(0, 12, 2))
    return mac_limpo(texto) or ""


def cabe_mais_um(ocupacao: Ocupacao, *, com_mic: bool) -> tuple[bool, Ocupacao]:
    """``(cabe?, como ficaria)`` — a pergunta do planejamento."""
    depois = _somar(ocupacao, com_mic=com_mic)
    from hefesto_dualsense4unix.integrations.radio_da_mesa import PALAVRA_CHEIA

    return palavra_da_ocupacao(depois.fracao_total) != PALAVRA_CHEIA, depois


def ordem_dos_destinos(
    planos: Mapping[str, PlanoDoAdaptador],
    *,
    varrendo: Iterable[str] | None = None,
    exceto: str = "",
) -> list[PlanoDoAdaptador]:
    """A ordem dos destinos — a D8 dela, em UMA função."""
    em_busca = {_hex(e) for e in (varrendo or ()) if _hex(e)}
    alvo_fora = _hex(exceto)
    candidatos = [
        p
        for endereco, p in planos.items()
        if endereco != SEM_ADAPTADOR and (not alvo_fora or _hex(endereco) != alvo_fora)
    ]
    return sorted(
        candidatos,
        key=lambda p: (_hex(p.endereco) in em_busca, -p.vaga_de_ponte, p.no_ar, p.endereco),
    )


def _quem_move(origem: PlanoDoAdaptador) -> tuple[str, str] | None:
    """``(uniq, modo)`` do controle que sai da origem: o ÚLTIMO a chegar com ponte."""
    if origem.orcamento is None:
        return None
    com_ponte = [c for c in origem.orcamento.controles if c.ponte and c.uniq]
    if not com_ponte:
        return None
    escolhido = com_ponte[-1]
    return escolhido.uniq, str(escolhido.ponte)


def ordem_de_redistribuicao(
    planos: Mapping[str, PlanoDoAdaptador],
    *,
    varrendo: Iterable[str] | None = None,
) -> Redistribuicao | None:
    """A ordem de serviço — UM movimento —, ou ``None`` quando não há o que mover."""
    reais = {
        endereco: plano
        for endereco, plano in planos.items()
        if endereco != SEM_ADAPTADOR
    }
    alem = sorted(
        (p for p in reais.values() if p.pontes > p.n_max),
        key=lambda p: (-(p.pontes - p.n_max), p.endereco),
    )
    if not alem:
        return _ordem_que_equilibra(reais, varrendo=varrendo)
    origem = alem[0]
    quem = _quem_move(origem)
    if quem is None:
        return None
    controle, modo = quem
    for destino in ordem_dos_destinos(reais, varrendo=varrendo, exceto=origem.endereco):
        if destino.pontes + 1 > destino.n_max:
            continue
        na_origem = origem.pontes - 1
        no_destino = destino.pontes + 1
        return Redistribuicao(
            origem=origem.endereco,
            destino=destino.endereco,
            origem_na_tela=origem.nome_na_tela,
            destino_na_tela=destino.nome_na_tela,
            o_que_eu_vi=(
                f"{origem.pontes} pontes de som e vibração num adaptador que "
                f"comporta {origem.n_max}."
            ),
            por_que_importa=POR_QUE_IMPORTA,
            ganho_esperado=(
                f'o "{origem.nome_na_tela}" ficaria com {na_origem} de '
                f'{origem.n_max}, e o "{destino.nome_na_tela}" com {no_destino} '
                f"de {destino.n_max}."
            ),
            controle=controle,
            modo=modo,
            pontes_na_origem_depois=na_origem,
            pontes_no_destino_depois=no_destino,
            n_max=origem.n_max,
        )
    return None


def _quem_move_para_equilibrar(origem: PlanoDoAdaptador) -> tuple[str, str] | None:
    """``(uniq, modo)`` do controle que sai para equilibrar: o ÚLTIMO a chegar."""
    if origem.orcamento is None:
        return None
    com_uniq = [c for c in origem.orcamento.controles if c.uniq]
    sem_ponte = [c for c in com_uniq if not c.ponte]
    candidatos = sem_ponte or com_uniq
    if not candidatos:
        return None
    escolhido = candidatos[-1]
    return escolhido.uniq, str(escolhido.ponte or "")


def _ordem_que_equilibra(
    reais: Mapping[str, PlanoDoAdaptador],
    *,
    varrendo: Iterable[str] | None = None,
) -> Redistribuicao | None:
    """A ordem de serviço que EQUILIBRA quantos controles cada adaptador tem."""
    if len(reais) < 2:
        return None
    origem = min(reais.values(), key=lambda p: (-p.no_ar, p.endereco))
    quem = _quem_move_para_equilibrar(origem)
    if quem is None:
        return None
    controle, modo = quem
    for destino in ordem_dos_destinos(reais, varrendo=varrendo, exceto=origem.endereco):
        if origem.no_ar - destino.no_ar < DIFERENCA_QUE_EQUILIBRA:
            continue
        if modo and destino.pontes + 1 > destino.n_max:
            continue
        leva = 1 if modo else 0
        return Redistribuicao(
            origem=origem.endereco,
            destino=destino.endereco,
            origem_na_tela=origem.nome_na_tela,
            destino_na_tela=destino.nome_na_tela,
            o_que_eu_vi=(
                f"{origem.no_ar} controles num adaptador, e {destino.no_ar} "
                f'no "{destino.nome_na_tela}".'
            ),
            por_que_importa=POR_QUE_IMPORTA_O_NUMERO,
            ganho_esperado=(
                f'o "{origem.nome_na_tela}" ficaria com {origem.no_ar - 1} controles, '
                f'e o "{destino.nome_na_tela}" com {destino.no_ar + 1}.'
            ),
            controle=controle,
            modo=modo,
            pontes_na_origem_depois=origem.pontes - leva,
            pontes_no_destino_depois=destino.pontes + leva,
            n_max=origem.n_max,
        )
    return None


def selo_da_especificacao() -> str:
    """As 1600 fatias — especificação de terceiro, nunca medida aqui."""
    return (
        f"as {SLOTS_POR_SEGUNDO} fatias por segundo: especificação de "
        "terceiro (Bluetooth Classic, 625 µs por fatia)"
    )


def selo_do_medido() -> str:
    """O custo de UM controle — medido nesta casa, e só de um."""
    total_com_mic = HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC
    return (
        f"{_numero(HZ_INPUT_SEM_MIC)} sem microfone e "
        f"{_numero(total_com_mic)} com: medido aqui, A/B de 25/07/2026, "
        "e é UM controle"
    )


def selo_do_derivado() -> str:
    """A soma de N controles — derivada da conta, e nunca medida."""
    return "a soma de N controles: derivado da conta, e nunca medido"


def selo_das_procedencias(plano: PlanoDoAdaptador) -> tuple[str, ...]:
    """As três partes do selo, mais a confissão quando ela é devida."""
    partes = [selo_da_especificacao(), selo_do_medido(), selo_do_derivado()]
    if plano.agora.controles > ENSAIO_MAXIMO_DESTA_CASA:
        partes.append(frase_da_extrapolacao())
    return tuple(partes)


def frase_da_extrapolacao() -> str:
    """A confissão do que esta casa nunca mediu — e o número sai do ensaio."""
    return (
        "Esta conta soma o custo medido de UM controle. O maior ensaio desta "
        f"casa no rádio foi de {ENSAIO_MAXIMO_DESTA_CASA} — "
        f"{MESA_CHEIA_DESTA_CASA} ao mesmo tempo nunca foi medido."
    )


def microfone_nasce_ligado() -> bool:
    """O microfone nasce ligado? **Sim, desde 17/09/2026.**"""
    return True


def frase_do_preco_por_controle() -> str:
    """O preço do microfone em UM controle — os dois números, lado a lado."""
    total_com_mic = HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC
    hoje = (
        "Hoje ele nasce ligado assim que o controle conecta."
        if microfone_nasce_ligado()
        else "Hoje ele nasce desligado, e só você o liga."
    )
    return (
        f"Um controle no rádio ocupa {_numero(HZ_INPUT_SEM_MIC)} das "
        f"{SLOTS_POR_SEGUNDO} fatias sem microfone, e {_numero(total_com_mic)} "
        f"com ele ligado. {hoje}"
    )


def frase_da_capacidade_do_mic(quantos: int = MESA_CHEIA_DESTA_CASA) -> str:
    """O achado que muda a decisão: quem enche o adaptador é a QUANTIDADE."""
    quantos = max(1, quantos)
    sem = _somar(Ocupacao(), com_mic=False, quantos=quantos)
    com = _somar(Ocupacao(), com_mic=True, quantos=quantos)
    pontos = round((com.fracao_total - sem.fracao_total) * 100)
    return (
        f"Com {quantos} controles no mesmo adaptador, ligar o microfone de "
        f"todos sobe de {round(sem.slots_total)} para "
        f"{round(com.slots_total)} das {sem.slots_teto} fatias — "
        f"{pontos} pontos. Quem enche o adaptador é a quantidade de "
        "controles, não o microfone."
    )


def nomes_dos_jogadores(plano: PlanoDoAdaptador) -> str:
    """``"Jogadores 1 e 2"`` — e :data:`SEM_NUMERO` para quem não tem número."""
    numeros = [str(j) for j in plano.jogadores if j is not None]
    sem_numero = sum(1 for j in plano.jogadores if j is None)
    partes: list[str] = []
    if numeros:
        rotulo = "Jogadores" if len(numeros) > 1 else "Jogador"
        partes.append(f"{rotulo} {_lista_em_portugues(numeros)}")
    if sem_numero:
        partes.append(SEM_NUMERO if sem_numero == 1 else f"{sem_numero}x {SEM_NUMERO}")
    return ", ".join(partes) if partes else SEM_NUMERO


def linha_do_plano(plano: PlanoDoAdaptador) -> str:
    """A linha de um adaptador: nome, quem está nele, a conta e a palavra."""
    ocupacao = plano.agora
    quantos_com_mic = ocupacao.com_microfone
    if quantos_com_mic == 0:
        mic = "sem microfone"
    elif quantos_com_mic == ocupacao.controles:
        mic = "com microfone"
    else:
        mic = f"{quantos_com_mic} com microfone"
    return (
        f'Adaptador "{plano.nome_na_tela}" · {nomes_dos_jogadores(plano)}, '
        f"{mic}   {round(ocupacao.slots_total)}/{ocupacao.slots_teto}  "
        f"{ocupacao.rotulo}"
    )


def linha_do_cabe_mais_um(plano: PlanoDoAdaptador, *, com_mic: bool = True) -> str:
    """A pergunta do planejamento, respondida sem inventar controle nenhum."""
    cabe, depois = cabe_mais_um(plano.agora, com_mic=com_mic)
    com = "com microfone" if com_mic else "sem microfone"
    resposta = "sim" if cabe else "não"
    return (
        f'Cabe mais um controle {com} no "{plano.nome_na_tela}": {resposta} — '
        f"ficaria em {round(depois.slots_total)} de {depois.slots_teto}."
    )


def linha_do_declarado_que_nao_subiu(plano: PlanoDoAdaptador) -> str | None:
    """A segunda linha, quando o que ela quer não é o que está de pé."""
    pendentes = plano.declarado_que_nao_subiu
    if not pendentes:
        return None
    quantos = len(pendentes)
    if quantos == 1:
        return "O microfone de um controle deste adaptador ainda não subiu."
    return (
        f"O microfone de {quantos} controles deste adaptador ainda não subiu."
    )


def _lista_em_portugues(itens: Sequence[str]) -> str:
    """``["1", "2", "3"]`` → ``"1, 2 e 3"``."""
    if len(itens) <= 1:
        return "".join(itens)
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


def _inteiro(valor: Any) -> int | None:
    """Inteiro, ou ``None`` — nunca um número chutado a partir da posição."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    return None


__all__ = [
    "ADAPTADOR_DESCONHECIDO",
    "ADAPTADOR_SEM_NOME",
    "DIFERENCA_QUE_EQUILIBRA",
    "ENSAIO_MAXIMO_DESTA_CASA",
    "FRASE_DO_ADAPTADOR_UNICO",
    "MESA_CHEIA_DESTA_CASA",
    "POR_QUE_IMPORTA",
    "POR_QUE_IMPORTA_O_NUMERO",
    "SEM_NUMERO",
    "PlanoDoAdaptador",
    "Redistribuicao",
    "apelido_por_endereco",
    "cabe_mais_um",
    "frase_da_capacidade_do_mic",
    "frase_da_extrapolacao",
    "frase_do_preco_por_controle",
    "linha_do_cabe_mais_um",
    "linha_do_declarado_que_nao_subiu",
    "linha_do_plano",
    "microfone_nasce_ligado",
    "nomes_dos_jogadores",
    "ordem_de_redistribuicao",
    "ordem_dos_destinos",
    "plano_por_adaptador",
    "selo_da_especificacao",
    "selo_das_procedencias",
    "selo_do_derivado",
    "selo_do_medido",
]
