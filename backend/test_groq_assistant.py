import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import main
from groq_assistant import GroqShoppingAssistant

@patch.dict('os.environ', {'LLM_PROVIDER':'groq', 'GROQ_ENABLED':'true', 'GROQ_API_KEY':'groq-test-only-key'})
class GroqTests(unittest.TestCase):
    def fake_response(self,content,finish='stop'):
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,message=SimpleNamespace(content=content,refusal=None))])

    def test_groq_endpoint_schema_and_private_context(self):
        sdk=MagicMock()
        sdk.chat.completions.create.return_value=self.fake_response(json.dumps({'is_shopping':True,'search_message':'everyday under 2000'}))
        with patch('openai.OpenAI') as constructor:
            constructor.return_value.__enter__.return_value=sdk
            value=GroqShoppingAssistant().interpret('daily 2 hazaar',{}, {'tracking':{'email':'private@example.test'}})
        self.assertEqual(value,'everyday under 2000')
        self.assertEqual(constructor.call_args.kwargs['base_url'],'https://api.groq.com/openai/v1')
        self.assertEqual(constructor.call_args.kwargs['api_key'],'groq-test-only-key')
        args=sdk.chat.completions.create.call_args.kwargs
        self.assertTrue(args['response_format']['json_schema']['strict'])
        self.assertNotIn('private@example.test',json.dumps(args['messages']))

    def test_incomplete_output_is_rejected(self):
        sdk=MagicMock();sdk.chat.completions.create.return_value=self.fake_response('{"is_shopping":true}',finish='length')
        with patch('openai.OpenAI') as constructor:
            constructor.return_value.__enter__.return_value=sdk
            self.assertIsNone(GroqShoppingAssistant().interpret('red kurta',{},{}))

    def test_invalid_schema_falls_back(self):
        sdk=MagicMock();sdk.chat.completions.create.return_value=self.fake_response('{"is_shopping":"yes","search_message":"red"}')
        with patch('openai.OpenAI') as constructor:
            constructor.return_value.__enter__.return_value=sdk
            self.assertIsNone(GroqShoppingAssistant().interpret('red kurta',{},{}))

    def test_rate_limit_respects_retry_after_and_stops_calls(self):
        class RateLimitError(Exception):
            response=SimpleNamespace(headers={'retry-after':'120'})
        sdk=MagicMock();sdk.chat.completions.create.side_effect=RateLimitError()
        with patch('openai.OpenAI') as constructor, patch('openai_assistant.time.monotonic',return_value=100):
            constructor.return_value.__enter__.return_value=sdk
            assistant=GroqShoppingAssistant()
            self.assertIsNone(assistant.interpret('red kurta',{},{}))
            self.assertEqual(assistant._retry_after,220)
            self.assertIsNone(assistant.interpret('blue kurta',{},{}))
            self.assertEqual(sdk.chat.completions.create.call_count,1)

    def test_missing_groq_key_never_calls_openai(self):
        with patch.dict('os.environ',{'GROQ_API_KEY':'','OPENAI_API_KEY':'test-openai-key'}), patch('openai.OpenAI') as constructor:
            self.assertIsNone(GroqShoppingAssistant().interpret('red kurta',{},{}))
            constructor.assert_not_called()
            self.assertFalse(main.llm_status()['configured'])

    def test_provider_routing_and_grounded_products(self):
        main.reset_session('groq-test')
        with patch.object(main.groq_assistant,'interpret',return_value='everyday under 2000'), patch.object(main.openai_assistant,'interpret') as paid:
            result=main.chat(main.ChatRequest(message='daily do hazaar tak',session_id='groq-test'))
            paid.assert_not_called()
        self.assertEqual(result['language_model'],'groq')
        self.assertTrue(result['products'])
        self.assertTrue(all(p['price']<=2000 for p in result['products']))
        with patch.dict('os.environ',{'LLM_PROVIDER':'local'}):
            self.assertFalse(main.llm_status()['enabled'])

if __name__=='__main__':unittest.main()
