import unittest
from unittest.mock import patch
import main
from shopping_assistant import fresh_profile, update_profile, matches, decorate

class ShoppingTests(unittest.TestCase):
    def setUp(self):
        provider=patch.dict('os.environ',{'LLM_PROVIDER':'local'})
        provider.start();self.addCleanup(provider.stop)
        self.session = 'shopping-regression'
        main.reset_session(self.session)

    def ask(self, message, action=None):
        return main.chat(main.ChatRequest(message=message, session_id=self.session, action=action))

    def test_screenshot_conversation(self):
        self.ask('Everyday styles', 'everyday')
        greeting = self.ask('hi')
        self.assertTrue(greeting['show_menu'])
        self.assertFalse(greeting['profile']['collection'])
        for message, budget in [('I am looking for something festive under 1500',1500), ('something under 3000',3000)]:
            response = self.ask(message)
            self.assertTrue(response['products'])
            self.assertEqual(response['profile']['occasion'], 'festive')
            for product in response['products']:
                self.assertLessEqual(product['price'], budget)
                self.assertIn('festive', product['collections'])

    def test_switch_from_everyday(self):
        self.ask('Everyday', 'everyday')
        response = self.ask('festive under 1500')
        self.assertIsNone(response['profile']['collection'])
        self.assertTrue(response['products'])

    def test_budget_formats(self):
        for message, budget in [('under 1.5k',1500),('below \u20b91,500',1500),('budget is Rs 2000',2000),('within INR 2,500',2500)]:
            profile=fresh_profile()
            update_profile(profile,message)
            self.assertEqual(profile['budget'],budget)
        profile=fresh_profile()
        update_profile(profile,'between 1000 and 2000')
        self.assertEqual((profile['min_budget'],profile['budget']),(1000,2000))
        update_profile(profile,'1500','budget')
        self.assertEqual(profile['budget'],1500)

    def test_budget_before_occasion(self):
        response=self.ask('under 1500')
        self.assertEqual(response['intent'],'clarification')
        response=self.ask('festive wear')
        self.assertTrue(response['products'])
        self.assertTrue(all(p['price']<=1500 for p in response['products']))

    def test_strict_preferences(self):
        profile=fresh_profile()
        update_profile(profile,'red cotton straight embroidered kurta set in XL festive under 1500')
        product={'name':'Red Cotton Embroidered Straight Kurta Pant Dupatta Set | Festive Ethnic Wear','category':'Suit Sets','color':'Red','price':1250,'fabric':'Cotton','style':'Straight','occasion':['Festive'],'features':['Embroidery'],'sizes':['M','XL','2XL'],'collections':['festive'],'stock':'unknown'}
        self.assertTrue(matches(product,profile))
        for changes in [{'price':2000},{'color':'Green'},{'fabric':'Rayon'},{'sizes':[]},{'category':'Co-ord Sets'},{'stock':'sold out'},{'style':'A-Line','name':'Red Cotton Embroidered A-Line Kurta Pant Dupatta Set | Festive Ethnic Wear'}]:
            with self.subTest(changes=changes):
                self.assertFalse(matches(dict(product,**changes),profile))

    def test_no_silent_relaxation(self):
        response=self.ask('festive under 1')
        self.assertFalse(response['products'])
        self.assertEqual(response['profile']['budget'],1)
        self.assertIn('exact match',response['reply'])

    def test_service_and_unknown_questions(self):
        for message in ['return policy','size guide','how can I contact support','what is the weather']:
            self.assertFalse(self.ask(message)['products'])
        self.assertEqual(self.ask('find a store')['intent'],'store_locator')

    def test_pagination_and_details(self):
        first=self.ask('festive under 3000')['products']
        detail=self.ask('details of the second one')
        self.assertEqual(detail['products'][0]['url'],first[1]['url'])
        second=self.ask('show more')['products']
        self.assertFalse({p['url'] for p in first}&{p['url'] for p in second})

    def test_hand_work_is_not_office(self):
        profile=fresh_profile()
        update_profile(profile,'hand work kurta')
        self.assertIsNone(profile['occasion'])

    def test_bad_catalogue_metadata(self):
        card=decorate({'name':'Purple Kurta','style':'Purple','image_url':'https://kiaasa.com/wp-content/uploads/2024/10/KIAASA.png'},fresh_profile())
        self.assertFalse(card['style'])
        self.assertTrue(card['image_unavailable'])

    def test_session_isolation(self):
        self.ask('festive under 1500')
        response=main.chat(main.ChatRequest(message='hi',session_id='new-shopping-user'))
        self.assertIsNone(response['profile']['budget'])
        self.assertEqual(main.customer_profiles[self.session]['budget'],1500)

if __name__=='__main__':
    unittest.main()
