import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import main
from openai_assistant import OpenAIShoppingAssistant, ShoppingInterpretation

class OpenAITests(unittest.TestCase):
    def setUp(self):
        provider = patch.dict('os.environ', {'LLM_PROVIDER':'openai'})
        provider.start()
        self.addCleanup(provider.stop)
        main.reset_session('openai-test')

    @patch.dict('os.environ', {'OPENAI_API_KEY':'', 'OPENAI_ENABLED':'true'})
    def test_missing_key_uses_local_without_call(self):
        assistant=OpenAIShoppingAssistant()
        self.assertIsNone(assistant.interpret('red kurta',{},{}))
        self.assertFalse(assistant.status()['configured'])

    @patch.dict('os.environ', {'OPENAI_API_KEY':'test-only-key', 'OPENAI_ENABLED':'true'})
    def test_structured_call_and_minimal_context(self):
        sdk=MagicMock()
        sdk.responses.parse.return_value=SimpleNamespace(output_parsed=ShoppingInterpretation(is_shopping=True, search_message='red everyday wear under 2000'))
        with patch('openai.OpenAI') as constructor:
            constructor.return_value.__enter__.return_value=sdk
            result=OpenAIShoppingAssistant().interpret('laal daily 2 hazaar',{}, {'awaiting':'budget','tracking':{'email':'private@example.test'}})
        self.assertEqual(result,'red everyday wear under 2000')
        args=sdk.responses.parse.call_args.kwargs
        self.assertFalse(args['store'])
        self.assertNotIn('private@example.test',args['input'])
        self.assertEqual(args['text_format'],ShoppingInterpretation)

    @patch.dict('os.environ', {'OPENAI_API_KEY':'test-only-key', 'OPENAI_ENABLED':'true'})
    def test_provider_error_falls_back_and_cools_down(self):
        sdk=MagicMock();sdk.responses.parse.side_effect=TimeoutError('private error details')
        with patch('openai.OpenAI') as constructor:
            constructor.return_value.__enter__.return_value=sdk
            assistant=OpenAIShoppingAssistant()
            self.assertIsNone(assistant.interpret('red kurta',{},{}))
            self.assertIsNone(assistant.interpret('blue kurta',{},{}))
            self.assertEqual(sdk.responses.parse.call_count,1)

    def test_hinglish_interpretation_returns_catalogue_products(self):
        with patch.object(main.openai_assistant,'interpret',return_value='everyday wear under 2000'):
            r=main.chat(main.ChatRequest(message='roz ke liye do hazaar tak',session_id='openai-test'))
        self.assertEqual(r['language_model'],'openai')
        self.assertTrue(r['products'])
        self.assertTrue(all(p['price']<=2000 and 'everyday' in p['collections'] for p in r['products']))
        source_urls={p['url'] for p in main.PRODUCTS}
        self.assertTrue(all(p['url'] in source_urls for p in r['products']))

    def test_explicit_budget_beats_incorrect_interpretation(self):
        with patch.object(main.openai_assistant,'interpret',return_value='festive under 5000'):
            r=main.chat(main.ChatRequest(message='festive under 1500',session_id='openai-test'))
        self.assertEqual(r['profile']['budget'],1500)
        self.assertTrue(all(p['price']<=1500 for p in r['products']))

    def test_service_menu_and_order_routes_skip_llm(self):
        with patch.object(main.openai_assistant,'interpret') as interpret:
            for message,action in [('hi',None),('Everyday','everyday'),('Where is my nearest store?',None),('track my order',None)]:
                main.chat(main.ChatRequest(message=message,session_id='openai-test',action=action))
            interpret.assert_not_called()

if __name__=='__main__': unittest.main()
