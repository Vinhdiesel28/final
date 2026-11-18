// DIAAGENTS - NEO4J DEMO QUERIES
// Safe read-only queries. Run each block separately in Neo4j Browser.
// Browser: http://127.0.0.1:7474  |  Database: neo4j

// 1. Active knowledge snapshot and number of current documents.
MATCH (k:DiaKnowledgeSnapshot {id: 'current'})
RETURN k.version AS snapshot_version,
       size(k.document_ids) AS current_documents;

// 2. Count current entity nodes, domain relationships and evidence links.
MATCH (k:DiaKnowledgeSnapshot {id: 'current'})
WITH k
OPTIONAL MATCH (s:DiaEntity)-[r:DIA_RELATION]->(o:DiaEntity)
WHERE r.snapshot = k.version
WITH k, collect(DISTINCT s) + collect(DISTINCT o) AS entity_nodes,
     count(r) AS domain_relationships
UNWIND entity_nodes AS entity_node
WITH k, count(DISTINCT entity_node) AS entities, domain_relationships
OPTIONAL MATCH (e:DiaEntity)-[support:SUPPORTED_BY]->(d:DiaDocument)
WHERE d.id IN k.document_ids
RETURN size(k.document_ids) AS documents,
       entities,
       domain_relationships,
       count(support) AS evidence_links;

// 3. Visual graph around A1C. Switch the result panel to Graph view.
MATCH (k:DiaKnowledgeSnapshot {id: 'current'})
WITH k
MATCH p=(s:DiaEntity)-[r:DIA_RELATION]->(o:DiaEntity)
WHERE r.snapshot = k.version
  AND (toLower(s.name) = 'a1c' OR toLower(o.name) = 'a1c')
RETURN p
LIMIT 30;

// 4. Traverse one or two hops from A1C, like the application GraphRAG step.
MATCH (k:DiaKnowledgeSnapshot {id: 'current'})
WITH k
MATCH p=(seed:DiaEntity {name: 'A1C'})-[:DIA_RELATION*1..2]-(related:DiaEntity)
WHERE all(edge IN relationships(p) WHERE edge.snapshot = k.version)
RETURN p
LIMIT 30;

// 5. Show the evidence documents supporting A1C knowledge.
MATCH (k:DiaKnowledgeSnapshot {id: 'current'})
WITH k
MATCH (entity:DiaEntity)-[:SUPPORTED_BY]->(document:DiaDocument)
WHERE toLower(entity.name) = 'a1c'
  AND document.id IN k.document_ids
RETURN entity.name AS entity,
       document.id AS document_id,
       document.title AS title,
       document.organization AS organization,
       document.url AS source_url
ORDER BY document_id;

// 6. Visual graph for type 2 diabetes and its directly connected knowledge.
MATCH (k:DiaKnowledgeSnapshot {id: 'current'})
WITH k
MATCH p=(s:DiaEntity)-[r:DIA_RELATION]->(o:DiaEntity)
WHERE r.snapshot = k.version
  AND (toLower(s.name) CONTAINS 'type 2' OR toLower(o.name) CONTAINS 'type 2')
RETURN p
LIMIT 40;

// 7. Inspect relationship labels and their evidence IDs in table form.
MATCH (k:DiaKnowledgeSnapshot {id: 'current'})
WITH k
MATCH (s:DiaEntity)-[r:DIA_RELATION]->(o:DiaEntity)
WHERE r.snapshot = k.version
RETURN s.name AS subject,
       r.relation AS predicate,
       o.name AS object,
       r.evidence AS evidence_id
ORDER BY subject, predicate
LIMIT 50;

// 8. Evidence-integrity check: every current relation should resolve to a document.
MATCH (k:DiaKnowledgeSnapshot {id: 'current'})
WITH k
MATCH (s:DiaEntity)-[r:DIA_RELATION]->(o:DiaEntity)
WHERE r.snapshot = k.version
OPTIONAL MATCH (d:DiaDocument {id: r.evidence})
RETURN count(r) AS checked_relationships,
       count(d) AS relationships_with_document,
       count(r) - count(d) AS missing_evidence_documents;

// 9. Search documents by a keyword used in the web demo.
MATCH (k:DiaKnowledgeSnapshot {id: 'current'})
WITH k
MATCH (d:DiaDocument)
WHERE d.id IN k.document_ids
  AND (toLower(d.title) CONTAINS 'a1c' OR toLower(d.text) CONTAINS 'a1c')
RETURN d.id, d.title, d.organization, d.url
LIMIT 20;
