# chronos/backend/app/utils/utils_graph.py

from neo4j import AsyncGraphDatabase
import os
import uuid
import asyncio
from dotenv import load_dotenv
import logging
from typing import Dict, Any, Optional

from ..models import Article

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables only if not in production
if not os.getenv("RENDER"):
    load_dotenv()  # Skip in Render (uses dashboard env vars)

# === Neo4j Configuration ===
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

logger.info(f"🌍 NEO4J_URI = {NEO4J_URI}")
logger.info(f"👤 NEO4J_USER = {NEO4J_USER}")
logger.info(f"🔑 NEO4J_PASSWORD is set = {bool(NEO4J_PASSWORD)}")

if not NEO4J_URI:
    logger.error("❌ NEO4J_URI is not set. Set it in environment.")
if not NEO4J_PASSWORD:
    logger.error("❌ NEO4J_PASSWORD is not set. Set it in environment.")

# Global driver instance
async def get_driver_with_retry(max_retries: int = 3, retry_delay: float = 1.0):
    """
    Get Neo4j driver with retry logic.
    Uses neo4j+s:// — so NO 'encrypted' or 'trust' flags.
    """
    global driver
    driver = None

    # Reuse healthy driver
    if 'driver' in globals() and driver is not None:
        try:
            async with driver.session() as session:
                await session.run("RETURN 1")
            logger.info("✅ Reusing existing healthy Neo4j connection")
            return driver
        except Exception:
            logger.warning("Existing driver is unhealthy, creating new one")
            await close_driver()

    for attempt in range(1, max_retries + 1):
        try:
            if not NEO4J_URI:
                raise ValueError("NEO4J_URI is not set")
            if not NEO4J_PASSWORD:
                raise ValueError("NEO4J_PASSWORD is not set")

            logger.info(f"🔌 Attempting Neo4j connection to {NEO4J_URI} (attempt {attempt})")

            driver = AsyncGraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
                connection_timeout=10,
                max_connection_lifetime=3600,
                max_connection_pool_size=10,
            )

            async with driver.session() as session:
                await session.run("RETURN 1")

            logger.info(f"✅ Neo4j connection established successfully on attempt {attempt}")
            return driver

        except Exception as e:
            logger.warning(f"⚠️ Neo4j connection attempt {attempt} failed: {str(e)}")
            await close_driver()

            if attempt < max_retries:
                backoff = retry_delay * (2 ** (attempt - 1))
                logger.info(f"🔁 Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
            else:
                logger.error(f"❌ Failed to connect to Neo4j after {max_retries} attempts")
                return None

    return None

async def get_driver():
    return await get_driver_with_retry()

async def close_driver():
    global driver
    if 'driver' in globals() and driver is not None:
        try:
            await driver.close()
            logger.info("🛑 Neo4j driver closed")
        except Exception as e:
            logger.error(f"Error closing Neo4j driver: {e}")
        finally:
            driver = None

async def execute_query_with_retry(
    query: str,
    parameters: Dict[str, Any] = None,
    max_retries: int = 3
):
    """
    Execute a Neo4j query with retry logic.
    Uses async iteration to collect records.
    """
    for attempt in range(1, max_retries + 1):
        try:
            db_driver = await get_driver_with_retry()
            if db_driver is None:
                raise ConnectionError("No Neo4j driver available")

            async with db_driver.session() as session:
                result = await session.run(query, parameters or {})
                records = [record async for record in result]  # Correct way to handle AsyncResult
                return records

        except Exception as e:
            logger.warning(f"⚠️ Query execution attempt {attempt} failed: {str(e)}")
            await close_driver()

            if attempt < max_retries:
                await asyncio.sleep(0.5 * attempt)
            else:
                logger.error(f"❌ Query failed after {max_retries} attempts: {str(e)}")
                raise

# === Node Creation & Retrieval Functions ===

async def create_historical_observation(text: str, source_id: str) -> str:
    node_id = f"hist-{uuid.uuid4()}"
    query = """
    CREATE (h:HistoricalObservation {
        id: $id,
        text: $text,
        source_id: $source_id,
        created_at: datetime()
    })
    RETURN h.id as id
    """
    try:
        records = await execute_query_with_retry(query, {
            "id": node_id,
            "text": text,
            "source_id": source_id
        })
        if not records:
            raise Exception("No records returned from Neo4j")
        record = records[0]  # Get the first record
        returned_id = record["id"]
        logger.info(f"✅ Created historical observation node: {returned_id}")
        return returned_id
    except Exception as e:
        logger.error(f"❌ Error creating historical observation: {str(e)}")
        raise

async def create_modern_study(article: Article) -> str:
    node_id = f"mod-{uuid.uuid4()}"
    query = """
    CREATE (m:ModernStudy {
        id: $id,
        pmid: $pmid,
        title: $title,
        authors: $authors,
        abstract: $abstract,
        publication_date: $publication_date,
        journal: $journal,
        doi: $doi,
        keywords: $keywords,
        created_at: datetime()
    })
    RETURN m.id as id
    """
    try:
        records = await execute_query_with_retry(query, {
            "id": node_id,
            "pmid": article.pmid,
            "title": article.title,
            "authors": article.authors,
            "abstract": article.abstract,
            "publication_date": article.publication_date,
            "journal": article.journal,
            "doi": article.doi,
            "keywords": article.keywords
        })
        if not records:
            raise Exception("No records returned from Neo4j")
        record = records[0]  # Get the first record
        returned_id = record["id"]
        logger.info(f"✅ Created modern study node: {returned_id}")
        return returned_id
    except Exception as e:
        logger.error(f"❌ Error creating modern study: {str(e)}")
        raise

async def get_node_by_id(node_id: str) -> Optional[Dict[str, Any]]:
    query = """
    MATCH (n)
    WHERE n.id = $id
    RETURN n
    """
    try:
        records = await execute_query_with_retry(query, {"id": node_id})
        if not records:
            logger.warning(f"🔍 Node not found: {node_id}")
            return None
        node = records[0]["n"]
        return dict(node.items())
    except Exception as e:
        logger.error(f"❌ Error retrieving node {node_id}: {str(e)}")
        raise

async def create_hypothesis_connection(hist_id: str, mod_id: str, hypothesis: str) -> str:
    rel_id = f"hyp-{uuid.uuid4()}"
    query = """
    MATCH (h:HistoricalObservation), (m:ModernStudy)
    WHERE h.id = $hist_id AND m.id = $mod_id
    CREATE (h)-[r:SUGGESTS_HYPOTHESIS {
        id: $rel_id,
        hypothesis: $hypothesis,
        created_at: datetime()
    }]->(m)
    RETURN r.id as id
    """
    try:
        records = await execute_query_with_retry(query, {
            "hist_id": hist_id,
            "mod_id": mod_id,
            "rel_id": rel_id,
            "hypothesis": hypothesis
        })
        if not records:
            raise Exception("No records returned from Neo4j")
        record = records[0]
        returned_id = record["id"]
        logger.info(f"✅ Created hypothesis connection: {returned_id}")
        return returned_id
    except Exception as e:
        logger.error(f"❌ Error creating hypothesis connection: {str(e)}")
        raise