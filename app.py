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

CONTEXTS = {
    "en": {
        "not-logged": ". Consider that I am not logged in.",
        "logged": ". Consider that my roles in the Profuturo platform are {}, I'm logged in, my username is {} and my first name is {}."
    },
    "es": {
        "not-logged": ". Considera que no estoy conectado.",
        "logged": ". Considera que mis roles en la plataforma Profuturo son {}, estoy conectado, mi nombre de usuario es {} y mi nombre es {}."
    },
    "pt_br": {
        "not-logged": ". Considere que não estou conectado.",
        "logged": ". Considere que meus papéis na plataforma Profuturo são {}, estou conectado, meu nome de usuário é {} e meu primeiro nome é {}."
    },
    "fr": {
        "not-logged": ". Considérez que je ne suis pas connecté.",
        "logged": ". Considérez que mes rôles dans la plateforme Profuturo sont {}, je suis connecté, mon nom d'utilisateur est {} et mon prénom est {}."
    },
}

COURSE = {
    "en": "Consider that I am enrolled in the course with {}.",
    "es": "Considera que estoy inscrito en el curso con id {}.",
    "pt_br": "Considere que estou matriculado no curso com id {}.",
    "fr": "Considérez que je suis inscrit aux cours avec id {}."
}

ROLE_NAMES = {
    "en": {
        "admin": "Administrator",
        "manager": "Manager",
        "coursecreator": "Course creator",
        "editingteacher": "Teacher",
        "teacher": "Non-editing teacher",
        "student": "Student",
        "guest": "Guest",
        "user": "Authenticated user",
        "frontpage": "Authenticated user on frontpage",
        "pfstudent": "Profuturo Student",
        "pfteacher": "Profuturo Teacher",
        "pfcoach": "Profuturo Coach",
        "countrycoordinator": "Country Coordinator"
        },
    "es": {
        "admin": "Administrador",
        "manager": "Administrador",
        "coursecreator": "Creador de cursos",
        "editingteacher": "Profesor",
        "teacher": "Profesor sin permisos de edición",
        "student": "Estudiante",
        "guest": "Invitado",
        "user": "Usuario autenticado",
        "frontpage": "Usuario autenticado en la página de inicio",
        "pfstudent": "Estudiante Profuturo",
        "pfteacher": "Profesor Profuturo",
        "pfcoach": "Coach Profuturo",
        "countrycoordinator": "Coordinador de país"
        },  
    "pt_br": {
        "admin": "Administrador",
        "manager": "Gerente",
        "coursecreator": "Criador de cursos",
        "editingteacher": "Professor",
        "teacher": "Professor sem permissões de edição",
        "student": "Estudante",
        "guest": "Convidado",
        "user": "Usuário autenticado",
        "frontpage": "Usuário autenticado na página inicial",
        "pfstudent": "Estudante Profuturo",
        "pfteacher": "Professor Profuturo",
        "pfcoach": "Coach Profuturo",
        "countrycoordinator": "Coordenador de país"
        },
    "fr": {
        "admin": "Administrateur",
        "manager": "Administrateur",
        "coursecreator": "Créateur de cours",
        "editingteacher": "Professeur",
        "teacher": "Professeur sans autorisation d'édition",
        "student": "Étudiant",
        "guest": "Invité",
        "user": "Utilisateur authentifié",
        "frontpage": "Utilisateur authentifié sur la page d'accueil",
        "pfstudent": "Étudiant Profuturo",
        "pfteacher": "Professeur Profuturo",
        "pfcoach": "Coach Profuturo",
        "countrycoordinator": "Coordinateur de pays"
        }
}  

PROHIBITED = {
    "pt_br": ["usuário", "administrador", "gerente", "criador de cursos", "professor"],
}


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
bedrock_runtime_agent_client = boto3_session.client('bedrock-agent-runtime', config=config)
runtime_client = boto3_session.client('bedrock-agent-runtime', config=config)
lambda_client = boto3_session.client('lambda', config=config)
iam_resource = boto3_session.resource('iam')
aoss_client = boto3_session.client('opensearchserverless', config=config)
s3_client = boto3_session.client("s3", config=config)
iam_client = boto3_session.client('iam')
postfix = os.environ['POSTFIX']

def send_message(message, agent_attributes, prompt_attributes, session_attributes, session_id):
    session_id = session_id
    message = message
    username = session_attributes['username']
    firstname = session_attributes['firstname']
    roles = prompt_attributes['roles']    
    roles_string = ', '.join(roles)
    course = prompt_attributes['course_id']
    locale = prompt_attributes['locale']

    if(username == ""):
        prompt = message + CONTEXTS[locale]["not-logged"]
    else:
        prompt = message + CONTEXTS[locale]["logged"].format(roles_string, username, firstname)
    
    prompt = prompt + COURSE[locale].format(course)
        
    response = bedrock_runtime_agent_client.invoke_agent(
        agentId=agent_attributes['agent_id'],
        agentAliasId=agent_attributes['agent_alias_id'],
        sessionId=session_id,
        inputText=prompt
    )
    
    completion = ""

    for event in response.get("completion"):
        chunk = event["chunk"]
        completion += chunk["bytes"].decode()

    return completion


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
        aws_data = request.json['aws_data']
        course_data = request.json['course_data']
        knowledge_base = BedrockKnowledgeBase(
                kb_id=aws_data['kb_id'],
                kb_name=aws_data['kb_name'],
                kb_description="knoledge base",
                data_bucket_name=aws_data['bucket_name'],
                boto3_session=boto3_session,
                courseid=course_data['course_id']               
            )
        knowledge_base.setup_knowledge_base() 
        course_metadata = {'metadataAttributes': course_data }
        knowledge_base.upload_data_to_s3(content=json.dumps(course_data), file_name=str(course_data['course_id']), file_extension='.json')
        knowledge_base.upload_data_to_s3(content=json.dumps(course_metadata), file_name=f"{course_data['course_id']}.json.metadata", file_extension='.json')
        knowledge_base.start_ingestion_job()
        bedrock_agent_client.prepare_agent(
            agentId=aws_data['agent_id']
        )
        time.sleep(30)
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        response = bedrock_agent_client.create_agent_alias(
            agentAliasName=f"alias-{random_string}",
            agentId=aws_data['agent_id'],
            description='Alias',
        )

        alias_id = response["agentAlias"]["agentAliasId"]
        response = {'msg': 'Bot content updated', 'alias_id': alias_id}   
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
    session_attributes = request.json['session_parameters']
    prompt_attributes = request.json['prompt_parameters']
    agent_settings = request.json['agent_settings']
    
    response_text = send_message(message, agent_settings, prompt_attributes, session_attributes, session_id)
    
    response = {'msg': response_text}
    return response, 200

if __name__ == "__main__":
    from waitress import serve
    import logging
    import os
    print(os.environ['APP_HOST'])
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')
    serve(app, host="0.0.0.0", port="8000")
