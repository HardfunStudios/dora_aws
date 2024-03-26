import os
from flask import Flask, render_template, request
from flask_cors import CORS
from bot_client import BotClient
from course_bot import CourseBot
from sync_client import SyncClient
import boto3
import botocore

config = botocore.config.Config(
    read_timeout=900,
    connect_timeout=900,
    retries={"max_attempts": 0},
    tcp_keepalive=True
)

boto3_session = boto3.session.Session(
    region_name='us-east-1',
    aws_access_key_id=os.environ['ACCESS_KEY'],
    aws_secret_access_key=os.environ['SECRET_KEY']
)

bedrock_agent_client = boto3_session.client('bedrock-agent', config=config)
runtime_client = boto3_session.client('bedrock-agent-runtime', config=config)
lambda_client = boto3_session.client('lambda', config=config)
iam_resource = boto3_session.resource('iam')
aoss_client = boto3_session.client('opensearchserverless', config=config)
s3_client = boto3_session.client("s3", config=config)

postfix = os.environ['POSTFIX']

bot_client = BotClient(
    bedrock_agent_client=bedrock_agent_client,
    runtime_client=runtime_client,
    lambda_client=lambda_client,
    iam_resource=iam_resource,
    postfix=postfix
)

sync_client = SyncClient(
    boto3_session=boto3_session,
    bedrock_agent_client=bedrock_agent_client,
    runtime_client=runtime_client,
    lambda_client=lambda_client,
    iam_resource=iam_resource,
    aoss_client=aoss_client,
    s3_client=s3_client,
    postfix=postfix
)

app = Flask(__name__)
app.debug = True
CORS(app, origins=['https://moodlefte.hardfunstudios.com'])

@app.route("/")
def home():    
    return render_template("chat.html", env=os.environ, value=os.environ['THEME'])

@app.route("/create", methods = ['POST'])
def create_course():
    course_id = request.json['course_id']
    try:
        response = bot_client.create_course_bot(course_id=course_id)
        return response, 200
    except Exception as e:
        return str(e), 500
    
@app.route("/sync", methods = ['POST'])
def sync_content():
    course_id = request.json['course_id']
    course_content = request.json['course_content']
    agent_id = request.json['agent_id']
    try:
        response = sync_client.create_course_knowledge_base(course_id=course_id, course_content=course_content)
        bot_client._prepare_agent(agent_id=agent_id)
        return response, 200
    except Exception as e:
        return str(e), 500
    
@app.route("/delete", methods = ['POST'])
def delete_course():
    course_id = request.json['course_id']
    print(course_id)
    try:
        response = bot_client.delete_course_bot(course_id=course_id)
        return response, 200
    except Exception as e:
        return str(e), 500
    

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
    import os
    print(os.environ['APP_HOST'])
    serve(app, host="0.0.0.0", port="8000")
