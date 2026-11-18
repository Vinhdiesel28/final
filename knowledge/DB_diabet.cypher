// Hybrid KB migration. Additive schema; preserves the existing Dia* graph.
CREATE CONSTRAINT kb_document_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT kb_chunk_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT kb_entity_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.canonical_id IS UNIQUE;
CREATE CONSTRAINT kb_version_unique IF NOT EXISTS FOR (v:KBVersion) REQUIRE v.id IS UNIQUE;
CREATE FULLTEXT INDEX kb_chunk_fulltext IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text, c.title];
CREATE VECTOR INDEX kb_chunk_vector IF NOT EXISTS FOR (c:Chunk) ON c.embedding
OPTIONS {indexConfig: {`vector.dimensions`:128, `vector.similarity_function`:'cosine'}};

// The Python ingestion tool loads stable-ID records using parameterized MERGE.
// Run individual read-only demo blocks below in Neo4j Browser AFTER ingestion.
MATCH (k:KBVersion {id:'current'}) RETURN k;

MATCH (k:KBVersion {id:'current'})
MATCH p=(d:Document)-[:HAS_CHUNK]->(c:Chunk)
WHERE c.id IN k.chunk_ids
RETURN p LIMIT 30;

MATCH (k:KBVersion {id:'current'})
MATCH p=(c:Chunk)-[m:MENTIONS]->(e:Entity)
WHERE c.id IN k.chunk_ids AND m.kb_version=k.version
RETURN p LIMIT 30;

SHOW INDEXES YIELD name, type, state WHERE name STARTS WITH 'kb_' RETURN name,type,state;
