import unittest
from catalogue_overrides import apply_catalogue_overrides
from shopping_assistant import matches, fresh_profile, decorate

URL='https://www.kiaasa.in/product/red-cotton-festive-kurta-pant-set-with-mirror-embroidery-digital-print-premium-ethnic-wear-kiaasa-trusted-quality'

class ColourReviewTests(unittest.TestCase):
    def product(self):
        return {'name':'Red Cotton Festive Kurta Pant Set','category':'Suit Sets','color':'Red','price':1500,'url':URL,'stock':'unknown'}
    def test_review_survives_fresh_import(self):
        original=self.product()
        result=apply_catalogue_overrides([original])[0]
        self.assertTrue(result['color_review_required'])
        self.assertNotIn('color_review_required',original)
        self.assertEqual(result['color'],'Red')
    def test_disputed_item_is_not_a_red_or_pink_match(self):
        product=apply_catalogue_overrides([self.product()])[0]
        for colour in ['red','pink']:
            profile=fresh_profile();profile['colors']=[colour]
            self.assertFalse(matches(product,profile))
        self.assertTrue(matches(product,fresh_profile()))
        self.assertIn('Needs confirmation',decorate(product,fresh_profile())['color'])
    def test_unaffected_red_product_is_still_recommended(self):
        product=self.product();product['url']='https://www.kiaasa.in/product/another-red-kurta'
        product=apply_catalogue_overrides([product])[0]
        profile=fresh_profile();profile['colors']=['red']
        self.assertTrue(matches(product,profile))

if __name__=='__main__':unittest.main()
