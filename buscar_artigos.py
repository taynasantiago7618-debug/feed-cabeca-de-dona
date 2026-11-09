#!/usr/bin/env python3
"""
Buscador do Feed Científico Cabeça de Dona.

Lê os temas em config.json, busca artigos novos no PubMed (com resumo)
e notícias científicas nos feeds RSS, e salva tudo em artigos.json.
A página (index.html) lê esse arquivo para montar o feed.

Usa só a biblioteca padrão do Python: não precisa instalar nada.
Uso: python3 buscar_artigos.py
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent
CONFIG = PASTA / "config.json"
SAIDA = PASTA / "artigos.json"

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "FeedCabecaDeDona/1.0 (leitor de artigos cientificos)"
AGORA = datetime.now(timezone.utc)

ROTULOS_CONCLUSAO = ("CONCLUSION", "CONCLUSIONS", "INTERPRETATION", "CONCLUSIONS AND RELEVANCE",
                     "IMPLICATIONS", "MAIN CONCLUSIONS", "SIGNIFICANCE")

TIPOS_DESTACADOS = {
    "Meta-Analysis": "Meta-análise",
    "Systematic Review": "Revisão sistemática",
    "Randomized Controlled Trial": "Ensaio clínico randomizado",
    "Clinical Trial": "Ensaio clínico",
    "Review": "Revisão",
    "Guideline": "Diretriz",
    "Practice Guideline": "Diretriz",
    "Observational Study": "Estudo observacional",
}


# ── Utilidades ────────────────────────────────────────────────────────────────

def baixar(url: str, tentativas: int = 3) -> bytes:
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as erro:  # noqa: BLE001
            if i == tentativas - 1:
                raise
            print(f"   aviso: falha ao baixar ({erro}), tentando de novo...")
            time.sleep(2 + i * 2)
    return b""


def texto(el) -> str:
    """Junta o texto de um elemento XML, incluindo tags internas (itálico etc.)."""
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def limpar_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def frases(s: str) -> list[str]:
    return [f.strip() for f in re.split(r"(?<=[.!?])\s+(?=[A-Z])", s) if f.strip()]


def montar_destaque(secoes: list[dict]) -> str:
    """O 'Em resumo' do cartão: a conclusão do estudo, ou as últimas frases do resumo."""
    for s in secoes:
        if (s.get("rotulo") or "").upper().strip(" :") in ROTULOS_CONCLUSAO:
            return s["texto"]
    corpo = " ".join(s["texto"] for s in secoes)
    fs = frases(corpo)
    if len(fs) <= 3:
        return corpo
    return " ".join(fs[-2:])


# ── PubMed ────────────────────────────────────────────────────────────────────

def pubmed_buscar_ids(consulta: str, dias: int, maximo: int) -> list[str]:
    params = {
        "db": "pubmed",
        "term": f"{consulta} AND hasabstract[text] AND english[lang]",
        "retmax": maximo,
        "sort": "pub_date",
        "datetype": "edat",
        "reldate": dias,
        "retmode": "json",
    }
    dados = json.loads(baixar(f"{EUTILS}/esearch.fcgi?{urllib.parse.urlencode(params)}"))
    return dados.get("esearchresult", {}).get("idlist", [])


def pubmed_data(artigo) -> datetime:
    for status in ("pubmed", "entrez"):
        d = artigo.find(f".//PubmedData/History/PubMedPubDate[@PubStatus='{status}']")
        if d is not None:
            try:
                return datetime(int(texto(d.find("Year"))), int(texto(d.find("Month"))),
                                int(texto(d.find("Day"))), tzinfo=timezone.utc)
            except ValueError:
                pass
    return AGORA


def pubmed_detalhes(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
    raiz = ET.fromstring(baixar(f"{EUTILS}/efetch.fcgi?{urllib.parse.urlencode(params)}"))
    itens = []
    for art in raiz.findall("PubmedArticle"):
        cit = art.find("MedlineCitation")
        pmid = texto(cit.find("PMID"))
        a = cit.find("Article")
        titulo = texto(a.find("ArticleTitle")).rstrip(".")
        secoes = []
        for parte in a.findall("Abstract/AbstractText"):
            t = texto(parte)
            if t:
                secoes.append({"rotulo": (parte.get("Label") or "").title(), "texto": t})
        if not titulo or not secoes:
            continue

        autores = []
        for au in a.findall("AuthorList/Author"):
            sobrenome = texto(au.find("LastName"))
            if sobrenome:
                autores.append(f"{sobrenome} {texto(au.find('Initials'))}".strip())
            elif au.find("CollectiveName") is not None:
                autores.append(texto(au.find("CollectiveName")))
        autores_txt = ", ".join(autores[:3]) + (" et al." if len(autores) > 3 else "")

        tipos = [texto(t) for t in a.findall("PublicationTypeList/PublicationType")]
        tipo = next((TIPOS_DESTACADOS[t] for t in TIPOS_DESTACADOS if t in tipos), "")

        doi = ""
        for aid in art.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = texto(aid)

        itens.append({
            "id": f"pmid-{pmid}",
            "fonte": "PubMed",
            "tipo_fonte": "artigo",
            "titulo": titulo,
            "revista": texto(a.find("Journal/ISOAbbreviation")) or texto(a.find("Journal/Title")),
            "autores": autores_txt,
            "tipo_estudo": tipo,
            "destaque": montar_destaque(secoes),
            "resumo": secoes,
            "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "doi": f"https://doi.org/{doi}" if doi else "",
            "data": pubmed_data(art).isoformat(),
        })
    return itens


# ── Notícias (RSS) ────────────────────────────────────────────────────────────

def ler_rss(url: str) -> list[dict]:
    raiz = ET.fromstring(baixar(url))
    itens = []
    for item in raiz.iter("item"):
        titulo = limpar_html(texto(item.find("title")))
        link = texto(item.find("link"))
        descricao = limpar_html(texto(item.find("description")))
        data = AGORA
        if item.find("pubDate") is not None:
            try:
                data = parsedate_to_datetime(texto(item.find("pubDate")))
                if data.tzinfo is None:
                    data = data.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
        if titulo and link:
            itens.append({"titulo": titulo, "link": link, "descricao": descricao, "data": data})
    return itens


def temas_da_noticia(conteudo: str, temas: list[dict]) -> list[str]:
    conteudo = conteudo.lower()
    achados = []
    for t in temas:
        for p in t["palavras"]:
            if re.search(rf"\b{re.escape(p.lower())}\b", conteudo):
                achados.append(t["slug"])
                break
    return achados


# ── Principal ─────────────────────────────────────────────────────────────────

def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    temas = cfg["temas"]
    aj = cfg["ajustes"]

    anteriores = {}
    if SAIDA.exists():
        try:
            for a in json.loads(SAIDA.read_text(encoding="utf-8")).get("artigos", []):
                anteriores[a["id"]] = a
        except (json.JSONDecodeError, KeyError):
            print("aviso: artigos.json anterior estava ilegível, começando do zero.")

    novos: dict[str, dict] = {}

    def juntar(item: dict, slugs: list[str]) -> None:
        atual = novos.get(item["id"]) or anteriores.get(item["id"])
        if atual:
            atual = {**atual, **{k: v for k, v in item.items() if k != "temas"}}
            atual["temas"] = sorted(set(atual.get("temas", [])) | set(slugs))
        else:
            atual = {**item, "temas": sorted(set(slugs)), "visto_em": AGORA.isoformat()}
        novos[item["id"]] = atual

    print("Buscando artigos no PubMed...")
    for t in temas:
        try:
            ids = pubmed_buscar_ids(t["pubmed"], aj["dias_busca"], aj["maximo_por_tema_por_busca"])
            time.sleep(0.4)
            detalhes = pubmed_detalhes(ids)
            time.sleep(0.4)
            for d in detalhes:
                juntar(d, [t["slug"]])
            print(f"   {t['nome']}: {len(detalhes)} artigos com resumo")
        except Exception as erro:  # noqa: BLE001
            print(f"   {t['nome']}: falhou ({erro})")

    print("Buscando notícias científicas...")
    for feed in cfg.get("feeds_noticias", []):
        try:
            contagem = 0
            for n in ler_rss(feed["url"]):
                if n["data"] < AGORA - timedelta(days=aj["dias_busca"]):
                    continue
                slugs = temas_da_noticia(f"{n['titulo']} {n['descricao']}", temas)
                if not slugs or not n["descricao"]:
                    continue
                juntar({
                    "id": "rss-" + re.sub(r"[^a-z0-9]+", "-", n["link"].lower())[-80:],
                    "fonte": feed["nome"].split(" · ")[0],
                    "tipo_fonte": "noticia",
                    "titulo": n["titulo"],
                    "revista": "",
                    "autores": "",
                    "tipo_estudo": "",
                    "destaque": n["descricao"],
                    "resumo": [],
                    "link": n["link"],
                    "doi": "",
                    "data": n["data"].isoformat(),
                }, slugs)
                contagem += 1
            print(f"   {feed['nome']}: {contagem} notícias nos seus temas")
        except Exception as erro:  # noqa: BLE001
            print(f"   {feed['nome']}: falhou ({erro})")

    # Junta com o histórico, descarta o que é antigo demais e limita por tema.
    todos = {**anteriores, **novos}
    limite = AGORA - timedelta(days=aj["manter_por_dias"])
    lista = [a for a in todos.values() if datetime.fromisoformat(a["data"]) >= limite]
    lista.sort(key=lambda a: a["data"], reverse=True)

    por_tema: dict[str, int] = {}
    final = []
    for a in lista:
        if any(por_tema.get(s, 0) < aj["maximo_por_tema_no_feed"] for s in a["temas"]):
            final.append(a)
            for s in a["temas"]:
                por_tema[s] = por_tema.get(s, 0) + 1

    SAIDA.write_text(json.dumps({
        "atualizado_em": AGORA.isoformat(),
        "titulo": cfg["titulo"],
        "subtitulo": cfg["subtitulo"],
        "temas": [{k: t[k] for k in ("slug", "nome", "cor")} for t in temas],
        "artigos": final,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    entraram = len([a for a in final if a["id"] not in anteriores])
    print(f"\nPronto: {len(final)} itens no feed ({entraram} novos nesta busca).")


if __name__ == "__main__":
    main()
