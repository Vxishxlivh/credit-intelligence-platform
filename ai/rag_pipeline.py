# ================================
# Credit Intelligence Platform
# RAG Pipeline — SEC Filing Q&A
# ================================

import os
import requests
import time
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Persistent storage for embeddings
CHROMA_DB_PATH = "./chroma_db"

HEADERS = {
    "User-Agent": os.getenv(
        "EDGAR_USER_AGENT",
        "credit-platform research@example.com"
    )
}


# ================================
# Fetch 10-K Filing Text from EDGAR
# ================================
def fetch_10k_text(cik: str, company_name: str) -> str:
    """
    Fetches the most recent 10-K filing text from SEC EDGAR.

    Args:
        cik: 10-digit company CIK
        company_name: used for logging only

    Returns:
        Raw text of the 10-K filing
    """
    logger.info(f"📄 Fetching 10-K for {company_name} (CIK: {cik})")

    # Get list of filings
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()

        filings = data.get("filings", {}).get("recent", {})
        forms   = filings.get("form", [])
        accessions = filings.get("accessionNumber", [])
        primary_docs = filings.get("primaryDocument", [])

        # Find most recent 10-K
        for i, form in enumerate(forms):
            if form == "10-K":
                accession = accessions[i].replace("-", "")
                doc       = primary_docs[i]

                # Build filing URL
                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/full-index/"
                    f"{accession[:4]}/{accession[4:6]}/"
                    f"{accession[6:8]}/{accession}/{doc}"
                )

                # Fetch the actual document
                doc_response = requests.get(
                    filing_url,
                    headers=HEADERS,
                    timeout=30
                )

                if doc_response.status_code == 200:
                    text = doc_response.text
                    # Clean up HTML tags if present
                    if "<html" in text.lower():
                        from html.parser import HTMLParser

                        class TextExtractor(HTMLParser):
                            def __init__(self):
                                super().__init__()
                                self.text_parts = []
                            def handle_data(self, data):
                                self.text_parts.append(data)

                        parser = TextExtractor()
                        parser.feed(text)
                        text = " ".join(parser.text_parts)

                    logger.info(
                        f"✅ Fetched 10-K for {company_name} "
                        f"({len(text):,} chars)"
                    )
                    return text

        logger.warning(f"No 10-K found for {company_name}")
        return ""

    except Exception as e:
        logger.error(f"Error fetching 10-K for {company_name}: {e}")
        return ""


# ================================
# Chunk and Embed Filing Text
# ================================
def embed_filing(company_name: str, text: str) -> Chroma:
    """
    Splits filing text into chunks and stores embeddings
    in a persistent ChromaDB vector store.

    Args:
        company_name: used as collection name
        text: full filing text

    Returns:
        Chroma vectorstore instance
    """
    logger.info(f"🔢 Embedding {company_name} filing...")

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = splitter.split_text(text)
    logger.info(f"   Split into {len(chunks)} chunks")

    # Create embeddings
    embeddings = OpenAIEmbeddings(
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    # Store in ChromaDB
    safe_name   = company_name.lower().replace(" ", "_")
    vectorstore = Chroma.from_texts(
        texts=chunks,
        embedding=embeddings,
        collection_name=safe_name,
        persist_directory=CHROMA_DB_PATH,
        metadatas=[{"company": company_name, "chunk": i}
                   for i in range(len(chunks))]
    )

    logger.info(f"✅ Embedded and stored {len(chunks)} chunks for {company_name}")
    return vectorstore


# ================================
# Load Existing Vectorstore
# ================================
def load_vectorstore(company_name: str) -> Chroma:
    """
    Load an existing ChromaDB vectorstore for a company.
    Use this after initial embedding to avoid re-embedding.
    """
    embeddings = OpenAIEmbeddings(
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    safe_name = company_name.lower().replace(" ", "_")

    return Chroma(
        collection_name=safe_name,
        embedding_function=embeddings,
        persist_directory=CHROMA_DB_PATH
    )


# ================================
# RAG Q&A Prompt
# ================================
RAG_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are a senior credit analyst at an alternative asset manager.
Answer the question below using ONLY the provided context from SEC filings.
Be specific, cite numbers where available, and flag if data is unclear.

Context from SEC filing:
{context}

Question: {question}

Answer (be concise and data-driven, 3-5 sentences max):
"""
)


# ================================
# Query the RAG Pipeline
# ================================
def query_filing(company_name: str, question: str) -> str:
    """
    Ask a credit analysis question against a company's SEC filing.

    Args:
        company_name: must match an embedded company name
        question: natural language credit question

    Returns:
        Answer string with source citations

    Example questions:
        "What is the leverage trend over the last 3 years?"
        "What are the main risk factors mentioned?"
        "Has the company breached any debt covenants?"
        "What is the maturity profile of their debt?"
    """
    logger.info(f"🔍 Querying: {question}")

    # Load vectorstore
    vectorstore = load_vectorstore(company_name)

    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    # Build retrieval chain
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(
            search_kwargs={"k": 4}   # retrieve top 4 chunks
        ),
        chain_type_kwargs={"prompt": RAG_PROMPT},
        return_source_documents=True
    )

    # Run query
    result = qa_chain.invoke({"query": question})

    answer   = result["result"]
    sources  = result["source_documents"]

    logger.info(f"✅ Answer generated ({len(sources)} source chunks used)")

    return answer


# ================================
# Ingest Multiple Companies
# ================================
def ingest_companies(companies: list):
    """
    Fetch and embed 10-K filings for multiple companies.
    Run this once to build your vector database.

    Args:
        companies: list of dicts with 'name' and 'cik' keys

    Example:
        ingest_companies([
            {"name": "Ford Motor", "cik": "0000037996"},
            {"name": "General Motors", "cik": "0001467858"}
        ])
    """
    logger.info(f"🚀 Ingesting {len(companies)} companies...")

    for company in companies:
        name = company["name"]
        cik  = company["cik"].zfill(10)

        # Fetch filing
        text = fetch_10k_text(cik, name)

        if not text:
            logger.warning(f"⚠️  Skipping {name} — no filing text")
            continue

        # Embed and store
        embed_filing(name, text)

        # Respect rate limits
        time.sleep(1)

    logger.info("✅ Ingestion complete")


# ================================
# Entry Point
# ================================
if __name__ == "__main__":
    # Step 1 — Ingest filings (run once)
    companies = [
        {"name": "Ford Motor",      "cik": "0000037996"},
        {"name": "General Motors",  "cik": "0001467858"},
        {"name": "Tesla",           "cik": "0001318605"},
    ]
    ingest_companies(companies)

    # Step 2 — Query example
    answer = query_filing(
        company_name = "Ford Motor",
        question     = "What is the leverage trend over the last 3 years?"
    )
    print("\n📊 Answer:")
    print(answer)