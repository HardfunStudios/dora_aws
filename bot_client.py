import boto3
import os

class BotClient:
    def __init__(self):
        self.client = boto3.client(
            service_name='bedrock-agent-runtime',
            region_name='us-east-1',
            aws_access_key_id=os.environ['ACCESS_KEY'],
            aws_secret_access_key=os.environ['SECRET_KEY']
        )

    def send_message(self, prompt, session_id, session_attributes, prompt_attributes):
        
        session_state = {
            "sessionAttributes": session_attributes,
            "promptAttributes": prompt_attributes
        }
        
        response = self.client.invoke_agent(
            agentId=os.environ['AGENT_ID'],
            agentAliasId=os.environ['AGENT_ALIAS_ID'],
            sessionId=session_id,
            inputText=prompt,
            sessionState=session_state
        )

        completion = ""
        for event in response.get("completion"):
            chunk = event["chunk"]
            completion += chunk["bytes"].decode()

        return completion