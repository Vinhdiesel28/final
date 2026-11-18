import importlib.util,json,os,sys,tempfile,unittest,warnings
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from qdrant_client import QdrantClient
from services.qdrant_backend import collection_name,upload,HybridQdrant

spec=importlib.util.spec_from_file_location('migration',Path(__file__).resolve().parents[1]/'tools/kb/migrate_cloud_kb.py')
migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)

class CloudKBTests(unittest.TestCase):
 def test_qdrant_copy_is_idempotent_and_preserves_citation_payload(self):
  client=QdrantClient(':memory:');self.addCleanup(client.close)
  version='a'*64;name=collection_name('hybrid',version)
  rows=[{'id':'chunk_a','text':'Synthetic evidence A','page_start':3,'embedding':[1.,0.]},
        {'id':'chunk_b','text':'Synthetic evidence B','page_start':9,'embedding':[0.,1.]}]
  with warnings.catch_warnings():
   warnings.simplefilter('ignore')
   upload(client,name,rows,[[1.,0.],[0.,1.]],version)
   upload(client,name,rows,[[1.,0.],[0.,1.]],version)
  self.assertEqual(client.count(name,exact=True).count,2)
  with patch('services.qdrant_backend.cloud_client',return_value=client):remote=HybridQdrant(version)
  result=remote.search([1.,0.])
  self.assertEqual(result[0]['doc']['id'],'chunk_a');self.assertEqual(result[0]['doc']['page_start'],3)
  self.assertEqual(result[0]['doc']['text'],'Synthetic evidence A')
 def test_qdrant_refuses_version_with_wrong_vector_schema(self):
  client=QdrantClient(':memory:');self.addCleanup(client.close);name=collection_name('hybrid','a'*64)
  with warnings.catch_warnings():
   warnings.simplefilter('ignore');upload(client,name,[{'id':'a'}],[[1.,0.]],'a'*64)
  with self.assertRaises(ValueError):upload(client,name,[{'id':'a'}],[[1.,0.,0.]],'a'*64)
 def test_missing_cloud_config_does_not_use_local_credentials(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
   with self.assertRaises(ValueError):migration.read_config(Path(directory)/'missing')
 def test_qdrant_only_config_does_not_weaken_full_migration_validation(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
   path=Path(directory)/'.env.cloud'
   path.write_text('NEO4J_URI=https://console.neo4j.io/projects/example/instances\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=fixture\nQDRANT_URL=https://fixture.cloud.qdrant.io\nQDRANT_API_KEY=fixture\n',encoding='utf-8')
   self.assertIn('QDRANT_URL',migration.read_config(path,require_neo4j=False))
   with self.assertRaises(ValueError):migration.read_config(path)
 def test_activation_preserves_unrelated_secrets_and_has_no_duplicate_keys(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
   path=Path(directory)/'.env';path.write_text('# Keep this\nLLM_API_KEY=fixture-key\nNEO4J_URI=local\nNEO4J_URI=duplicate\n',encoding='utf-8')
   migration.activate(path,{'NEO4J_URI':'neo4j+s://example.invalid','QDRANT_URL':'https://example.invalid'})
   result=path.read_text(encoding='utf-8')
   self.assertIn('LLM_API_KEY=fixture-key',result);self.assertIn('# Keep this',result)
   self.assertEqual(result.count('NEO4J_URI='),1)
 def test_collection_names_cannot_target_arbitrary_paths(self):
  with self.assertRaises(ValueError):collection_name('hybrid','a'*64,'../../other')
