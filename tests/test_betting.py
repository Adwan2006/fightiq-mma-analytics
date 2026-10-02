import csv
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import betting
import import_fighters
from import_odds import ingest
import app as application

FIELDS = ['r_fighter','b_fighter','r_odds','b_odds','date','winner','weight_class','gender']

def dataset(rows):
    out=io.StringIO(); writer=csv.writer(out);writer.writerow(FIELDS);writer.writerows(rows);return out.getvalue()

class HistoricalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=Path(self.temp.name)/'test.db'
    def tearDown(self): self.temp.cleanup()
    def seed(self):
        rows=[
            ['A','B',-200,170,'2020-01-01','Blue','Lightweight','MALE'],
            ['A','C',-150,-110,'2020-02-01','Red','Lightweight','MALE'],
            ['B','C',100,-100,'2020-03-01','Red','Lightweight','MALE'],
            ['B','D','','200','2020-04-01','Blue','Lightweight','MALE'],
            ['A','D',-300,250,'2020-05-01','Draw','Lightweight','MALE'],
            ['A','E',-300,250,'2020-06-01','No Contest','Lightweight','MALE'],
            ['F','G',120,180,'2020-07-01','Red','Flyweight','FEMALE'],
        ]
        text=dataset(rows);ingest(self.db,text);return text
    def test_denominators_and_two_negative_or_positive_prices(self):
        self.seed();rows,_=betting.load_bouts(self.db);s=betting.summary(rows)
        self.assertEqual((s['eligible'],s['underdog_wins'],s['favorite_wins']),(3,1,2))
        self.assertEqual(s['upset_rate'],33.3)
        self.assertEqual((s['missing'],s['tied'],s['non_decisive']),(1,1,2))
        d=betting.dashboard(rows)
        self.assertEqual(sum(b['total'] for b in d['buckets']),6)
        self.assertIn("Women's Flyweight",[b['label'] for b in d['divisions']])
    def test_import_idempotency_and_failed_import_preserves_rows(self):
        text=self.seed();ingest(self.db,text)
        self.assertEqual(len(betting.load_bouts(self.db)[0]),7)
        for invalid in ['bad,columns\na,b', dataset([]), text.replace('2020-01-01','bad-date')]:
            with self.assertRaises(ValueError):ingest(self.db,invalid)
        self.assertEqual(len(betting.load_bouts(self.db)[0]),7)
    def test_conflicting_duplicates_rejected(self):
        text=self.seed()
        conflicting=text+text.splitlines()[1].replace('Blue','Red')+'\n'
        with self.assertRaises(ValueError):ingest(self.db,conflicting)
    def test_records_upsets_and_name_matching(self):
        self.seed();rows,_=betting.load_bouts(self.db)
        context=betting.fighter_context(rows,{'name':'B'})
        self.assertEqual(context['records'][1]['wins'],1)
        self.assertEqual(context['biggest']['odds'],170)
        self.assertEqual(context['excluded'],2)
        self.assertEqual(betting.name_key('José Aldo'),betting.name_key('Jose Aldo'))
    def test_valid_odds_and_bucket_boundaries(self):
        for odd in [0,99,-99,'NA',None,float('nan'),float('inf')]:self.assertIsNone(betting.probability(odd))
        self.assertEqual(betting.probability(-100),betting.probability(100))
        for odds,index in [(-500,0),(-499,1),(-300,1),(-299,2),(-200,2),(-199,3),(-100,3),(100,4),(199,4),(200,5),(299,5),(300,6),(499,6),(500,7)]:
            self.assertEqual(betting.bucket(odds),betting.BUCKETS[index])
        self.assertIsNone(betting.summary([])['upset_rate'])
    def test_original_importer_preserves_ids_and_photos(self):
        with patch.object(import_fighters,'DATABASE',str(self.db)):
            import_fighters.recreate_database()
            csv_text='name,wins,losses,height,reach,weight\nTest Fighter,1,0,72,74,155\n'
            with patch.object(import_fighters,'download_csv',return_value=csv_text):
                import_fighters.import_fighters()
                with sqlite3.connect(self.db) as conn:
                    conn.execute("UPDATE fighters SET image_url='cached.jpg',image_checked=1")
                    before=conn.execute('SELECT id FROM fighters').fetchone()[0]
                import_fighters.recreate_database();import_fighters.import_fighters()
            with sqlite3.connect(self.db) as conn:
                self.assertEqual(conn.execute('SELECT id,image_url,image_checked FROM fighters').fetchall(),[(before,'cached.jpg',1)])
    def test_empty_betting_page(self):
        with patch.object(application,'DATABASE',str(self.db)):
            response=application.app.test_client().get('/betting')
            self.assertEqual(response.status_code,200)
            self.assertIn(b'No historical bouts',response.data)

class ExistingDatabaseIntegrationTests(unittest.TestCase):
    def test_existing_routes_and_new_sections(self):
        # Network photo lookup is separately preserved; avoid external services in tests.
        with patch.object(application,'ensure_fighter_image',side_effect=application.get_fighter_by_id):
            client=application.app.test_client()
            paths=['/','/fighters','/fighters?search=Islam','/analytics','/compare',
                   '/compare?fighter1=Islam+Makhachev&fighter2=Charles+Oliveira',
                   '/fighter/islam-makhachev','/api/fighter-search?q=Islam',
                   '/betting','/betting?year=2020',"/betting?division=Women's+Flyweight",'/betting?year=1800']
            for path in paths:
                with self.subTest(path=path):self.assertEqual(client.get(path).status_code,200)
            self.assertIn(b'Historical odds',client.get('/fighter/islam-makhachev').data)
            self.assertIn(b'Historical betting context',client.get(paths[5]).data)
            self.assertEqual(client.get('/fighter/no-such-fighter').status_code,404)
            self.assertEqual(client.get('/api/fighter-search?q=x').json,[])

if __name__=='__main__':unittest.main()
