import os
import json
from flask import Flask, render_template, request
from flask_cors import CORS
from bot_client import BotClient
from course_bot import CourseBot
from sync_client import SyncClient
import boto3
import botocore
import traceback
from knowledge_base import BedrockKnowledgeBase
import time
import random
import string

config = botocore.config.Config(
    read_timeout=1000,
    connect_timeout=1000,
    retries={"max_attempts": 15},
    tcp_keepalive=True
)

boto3_session = boto3.session.Session(
    region_name='us-east-1',
    aws_access_key_id=os.getenv('ACCESS_KEY'),
    aws_secret_access_key=os.getenv('SECRET_KEY')
)

bedrock_agent_client = boto3_session.client('bedrock-agent', config=config)
runtime_client = boto3_session.client('bedrock-agent-runtime', config=config)
lambda_client = boto3_session.client('lambda', config=config)
iam_resource = boto3_session.resource('iam')
aoss_client = boto3_session.client('opensearchserverless', config=config)
s3_client = boto3_session.client("s3", config=config)
iam_client = boto3_session.client('iam')
postfix = os.environ['POSTFIX']
app = Flask(__name__)
app.debug = True
CORS(app, origins=['https://moodlefte.hardfunstudios.com'])

@app.route("/")
def home():    
    return render_template("chat.html", env=os.environ, value=os.environ['THEME'])
    
@app.route("/sync", methods = ['POST'])
def sync_content():
    print("entrou no sync")
    
    try:    
        course_id = request.json['course_id']
        course_content = request.json['course_content']
        data = request.json['data']
        metadata = request.json['metadata']
        agent_data = request.json['agent_data']
        
        bucket_name = f"course-bot-{postfix}-{course_id}" 
        knowledge_base_name = f"course-bot-{postfix}-{course_id}"
        knowledge_base_description = f"Course bot for course {course_id}"
        knowledge_base = BedrockKnowledgeBase(
                kb_id=data if data else None,
                kb_name=knowledge_base_name,
                kb_description=knowledge_base_description,
                data_bucket_name=bucket_name,
                boto3_session=boto3_session,                
                courseid=course_id
            )
        if not data:
           knowledge_base.setup_knowledge_base() 
           bedrock_agent_client.associate_agent_knowledge_base(
                agentId=agent_data['agent_id'],
                agentVersion='DRAFT',
                description=f'Access knowledge base when user is on course_id {course_id}',
                knowledgeBaseId=knowledge_base.knowledgeBaseId,
                knowledgeBaseState='ENABLED'
            )
        
        knowledge_base.upload_data_to_s3(content=course_content, file_name=str(course_id), file_extension='.txt')
        knowledge_base.upload_data_to_s3(content=json.dumps(metadata), file_name=f"{course_id}.metadata", file_extension='.json')
        knowledge_base.start_ingestion_job()
        bedrock_agent_client.prepare_agent(
            agentId=agent_data['agent_id']
        )
        time.sleep(30)
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        response = bedrock_agent_client.create_agent_alias(
            agentAliasName=f"alias-{random_string}",
            agentId=agent_data['agent_id'],
            description='Course alias',
        )

        alias_id = response["agentAlias"]["agentAliasId"]
        response = {'msg': 'Course bot created successfully', 'alias_id': alias_id, 'kb_name': knowledge_base_name}   
        return response, 200
    except Exception as e:
        error_message = traceback.format_exc()
        return { 'error': error_message, 'access_key': os.getenv('ACCESS_KEY')}, 500
    
@app.route("/delete", methods = ['POST'])
def delete_course():
    course_id = request.json['course_id']
    try:
        sync_client = SyncClient(
            boto3_session=boto3_session,
            bedrock_agent_client=bedrock_agent_client,
            runtime_client=runtime_client,
            lambda_client=lambda_client,
            iam_resource=iam_resource,
            iam_client=iam_client,
            aoss_client=aoss_client,
            s3_client=s3_client,
            postfix=postfix
        )
        sync_client.delete_knowledge_base(course_id=course_id)        
        response = {'msg': 'Course bot deleted successfully'}
        return response, 200
    except Exception as e:
        error_message = traceback.format_exc()
        return error_message, 500
    

@app.route("/get", methods = ['POST'])
def get_response():
    session_id = request.json['session_id']
    message = request.json['msg']
    session_attributes = request.json['session_attributes']
    prompt_attributes = request.json['prompt_attributes']
    agent_settings = request.json['agent_settings']
    
    bot_client = BotClient()
    response_text = bot_client.send_message(
        prompt=message, 
        session_id=session_id, 
        session_attributes=session_attributes, 
        prompt_attributes=prompt_attributes, 
        agent_settings=agent_settings
    )
    
    response = {'msg': response_text}
    return response, 200

if __name__ == "__main__":
    from waitress import serve
    import logging
    import os
    print(os.environ['APP_HOST'])
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')
    serve(app, host="0.0.0.0", port="8000")
