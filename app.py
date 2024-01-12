import boto3
import os
from flask import Flask, render_template, request

client = boto3.client(
    service_name='bedrock-agent-runtime',
    region_name='us-east-1'
)

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
  
app = Flask(__name__)

@app.route("/")
def home():    
    return render_template("chat.html", env=os.environ, value="purple")

@app.route("/get", methods = ['POST'])
def get_response():
    session_id = request.json['session_id']
    message = request.json['msg']
    msg = send_message(message, session_id)
    response = {'msg': msg}
    return response, 200

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8000)
