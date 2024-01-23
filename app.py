import boto3
import os
from flask import Flask, render_template, request
from flask_cors import CORS
 
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

def send_message(prompt, session_id):
  response = client.invoke_agent(
    agentId=os.environ['AGENT_ID'],
    agentAliasId=os.environ['AGENT_ALIAS_ID'],
    sessionId=session_id,
    inputText=prompt
  )
  
  completion = ""

  for event in response.get("completion"):
      chunk = event["chunk"]
      completion += chunk["bytes"].decode()

  return completion   

client = boto3.client(
    service_name='bedrock-agent-runtime',
    region_name='us-east-1',
    aws_access_key_id=os.environ['ACCESS_KEY'],
    aws_secret_access_key=os.environ['SECRET_KEY']
)
app = Flask(__name__)
CORS(app)

@app.route("/")
def home():    
    return render_template("chat.html", env=os.environ, value=os.environ['THEME'])

@app.route("/get", methods = ['POST'])
def get_response():
    session_id = request.json['session_id']
    message = request.json['msg']
    username = request.json['username']
    firstname = request.json['firstname']
    roles = request.json['roles']
    
    locale = request.json['locale']
    
    #roles = [ROLE_NAMES[locale][role] for role in roles]
    
    roles_string = ', '.join(roles)
    if(username == ""):
        prompt = message + CONTEXTS[locale]["not-logged"]
    else:
        prompt = message + CONTEXTS[locale]["logged"].format(roles_string, username, firstname)
    msg = send_message(prompt, session_id)
    response = {'msg': msg}
    return response, 200

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8000)
