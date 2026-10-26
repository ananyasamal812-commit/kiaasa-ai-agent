"""Groq-hosted interpretation, using the existing OpenAI-compatible SDK."""
import json
import os
from openai_assistant import OpenAIShoppingAssistant, ShoppingInterpretation, INSTRUCTIONS

class GroqShoppingAssistant(OpenAIShoppingAssistant):
    def status(self):
        return {'provider':'groq',
                'enabled':os.getenv('GROQ_ENABLED','true').lower() not in {'false','0','no'},
                'configured':bool(os.getenv('GROQ_API_KEY','').strip()),
                'model':os.getenv('GROQ_MODEL','openai/gpt-oss-20b')}

    def _request(self, payload, status):
        from openai import OpenAI
        with OpenAI(api_key=os.environ['GROQ_API_KEY'],
                    base_url='https://api.groq.com/openai/v1',
                    timeout=12.0, max_retries=0) as client:
            response=client.chat.completions.create(
                model=status['model'],
                messages=[{'role':'system','content':INSTRUCTIONS},
                          {'role':'user','content':json.dumps(payload,ensure_ascii=False)}],
                response_format={'type':'json_schema', 'json_schema':{
                    'name':'shopping_interpretation', 'strict':True,
                    'schema':ShoppingInterpretation.model_json_schema()}},
                max_completion_tokens=1200,
            )
        if not response.choices or response.choices[0].finish_reason != 'stop':
            return None
        message=response.choices[0].message
        if getattr(message,'refusal',None) or not message.content:
            return None
        return ShoppingInterpretation.model_validate_json(message.content, strict=True)

groq_assistant=GroqShoppingAssistant()
