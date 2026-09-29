import datetime as dt
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from catalogue_coverage import reconcile, release_day, region_report


class CoverageTests(unittest.TestCase):
    today=dt.date(2026,9,29)

    def test_platform_date_precision_and_status(self):
        self.assertIsNone(release_day({'platform':6,'y':2015,'m':1,'d':1},self.today))
        self.assertIsNone(release_day({'platform':48,'y':2026},self.today))
        self.assertEqual(release_day({'platform':48,'y':2025},self.today),'2025-12-31')
        self.assertIsNone(release_day({'platform':48,'y':2026,'m':9},self.today))
        self.assertIsNone(release_day({'platform':48,'y':2020,'status':{'name':'Cancelled'}},self.today))
        self.assertIsNone(release_day({'platform':48,'y':2020,'status':{'name':'Early Access'}},self.today))
        self.assertEqual(release_day({'platform':165,'y':2019,'m':1,'d':4},self.today),'2019-01-04')

    def test_unique_titles_regional_variants_editions_and_legacy(self):
        def game(i,kind='Main Game',**kw):
            return {'id':i,'name':'Game '+str(i),'platforms':[48],'game_type':{'type':kind},**kw}
        def date(i,**kw):
            return {'game':i,'platform':48,'y':2020,'m':1,'d':1,**kw}
        ref={'games':[game(1),game(2,version_parent=1),game(3,'DLC'),game(4,platforms=[8]),
            game(5,platforms=[165]),game(6),game(7,'Season'),game(8,game_status={'status':'Cancelled'})],
            'release_dates':[date(1,release_region={'region':'Europe'}),date(1,release_region={'region':'North America'}),
                date(2),date(3),date(4,platform=8),date(5,platform=165),date(6,y=2027),date(7),date(8)]}
        entries=[{'canonical_id':1,'name':'One','links':[{'kind':'base','regions':['EUR']}], 'canonical_name':'One'},
            {'canonical_id':1,'name':'One USA','links':[{'kind':'update','regions':['USA']}]},
            {'canonical_id':4,'name':'Legacy','links':[]},
            {'canonical_id':'local:unknown','name':'Local','links':[]}]
        result=reconcile(ref,entries,{},self.today)
        self.assertEqual(result['summary']['reference_unique_games'],2)
        self.assertEqual(result['summary']['reference_matches'],1)
        self.assertEqual(result['summary']['reference_gaps'],1)
        self.assertEqual(result['summary']['catalogue_unique_identities'],3)
        self.assertEqual(result['summary']['local_without_ps4_reference'],1)
        row=result['reference'][0]
        self.assertEqual(row['base_regions'],['EUR'])
        self.assertEqual(row['package_regions'],['EUR','USA'])
        self.assertEqual(row['reference_regions'],['EUR','USA'])
        self.assertEqual(row['reference_ids'],[1,2])

    def test_a_link_is_not_a_second_unique_game(self):
        link={'url':'https://1fichier.com/?example','kind':'base','regions':['EUR'],'region_status':'identified'}
        data={'summary':{},'entries':[{'name':'One','canonical_id':1,'links':[link,link]},
            {'name':'One edition','canonical_id':1,'links':[link]}]}
        report=region_report(data)
        self.assertEqual(report['regions']['EUR']['links'],1)
        self.assertEqual(report['regions']['EUR']['identities'],1)
        self.assertEqual(report['regions']['EUR']['base_identities'],1)


if __name__ == '__main__': unittest.main()
