import boto3
import botocore
import os

class BotClient:
    def __init__(self):
        config = botocore.config.Config(
            read_timeout=900,
            connect_timeout=900,
            retries={"max_attempts": 0},
            tcp_keepalive=True
        )
        self.client = boto3.client(
            service_name='bedrock-agent-runtime',
            region_name='us-east-1',
            aws_access_key_id=os.environ['ACCESS_KEY'],
            aws_secret_access_key=os.environ['SECRET_KEY'],
            config=config
        )

    def send_message(self, prompt, session_id, session_attributes, prompt_attributes, agent_settings):
        
        session_state = {
            "sessionAttributes": session_attributes,
            "promptSessionAttributes": prompt_attributes
        }
        
        response = self.client.invoke_agent(
            agentId=agent_settings['agentid'],
            agentAliasId=agent_settings['agentaliasid'],
            sessionId=session_id,
            inputText=prompt,
            sessionState=session_state,
            enableTrace=True
        )
        return response.get("trace").get
        completion = ""
        for event in response.get("completion"):
            chunk = event["chunk"]
            completion += chunk["bytes"].decode()

