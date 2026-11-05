"""Neo4j is the document and entity source when KNOWLEDGE_BACKEND=neo4j."""
import os
import settings
from neo4j import GraphDatabase


class Neo4jStore:
    def __init__(self):
        self.driver = GraphDatabase.driver(os.environ.get('NEO4J_URI','bolt://127.0.0.1:7687'),
            auth=(os.environ.get('NEO4J_USER','neo4j'), os.environ['NEO4J_PASSWORD']))
        self.driver.verify_connectivity()
        self.database = os.environ.get('NEO4J_DATABASE','neo4j')

    def query(self, cypher, **params):
        with self.driver.session(database=self.database) as session:
            return [r.data() for r in session.run(cypher, **params)]

    def ingest(self, documents, edges):
        self.query('CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:DiaDocument) REQUIRE d.id IS UNIQUE')
        self.query('CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:DiaEntity) REQUIRE e.name IS UNIQUE')
        self.query('UNWIND $rows AS row MERGE (d:DiaDocument {id:row.id}) SET d += row', rows=documents)
        self.query('''UNWIND $rows AS row
            MERGE (s:DiaEntity {name:row.subject}) MERGE (o:DiaEntity {name:row.object})
            MERGE (s)-[r:DIA_RELATION {relation:row.relation, evidence:row.evidence}]->(o)
            WITH s,o,row MATCH (d:DiaDocument {id:row.evidence})
            MERGE (s)-[:SUPPORTED_BY]->(d) MERGE (o)-[:SUPPORTED_BY]->(d)''', rows=edges)

    def load(self):
        documents = [r['doc'] for r in self.query('MATCH (d:DiaDocument) RETURN properties(d) AS doc ORDER BY d.id')]
        edges = self.query('MATCH (s:DiaEntity)-[r:DIA_RELATION]->(o:DiaEntity) RETURN s.name AS subject, r.relation AS relation, o.name AS object, r.evidence AS evidence ORDER BY subject,relation,object')
        if not documents: raise RuntimeError('Neo4j corpus is empty; run tools/ingest_neo4j.py')
        return documents, edges

    def paths(self, seeds):
        return self.query('''MATCH (s:DiaEntity) WHERE s.name IN $seeds
            MATCH p=(s)-[:DIA_RELATION*1..2]-(o:DiaEntity)
            UNWIND relationships(p) AS r
            RETURN DISTINCT startNode(r).name AS subject, r.relation AS relation,
            endNode(r).name AS object, r.evidence AS evidence LIMIT 16''', seeds=seeds)
