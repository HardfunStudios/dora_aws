import os
from flask import Flask, render_template, request
from flask_cors import CORS
from bot_client import BotClient
from course_bot import CourseBot

bot_client = BotClient()

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():    
    return render_template("chat.html", env=os.environ, value=os.environ['THEME'])

@app.route("/create", methods = ['POST'])
def create_course():
    print(request.json)
    course_id = request.json['course_id']
    bot = CourseBot(course_id)
    try:
        response = {}
        response['bucket'] = bot.create_s3_bucket()
        response['data_source'] = bot.create_data_source()
        return response, 200

        response['knowledge_base'] = bot.create_knowledge_base()
        response['agent'] = bot.create_agent()
        return response, 200
    except Exception as e:
        return str(e), 500

@app.route("/sync", methods = ['POST'])
def sync_content():
    course_id = request.json['course_id']
    file_content = request.json['file_content']
    bot = CourseBot(course_id)
    try:
        response = bot.sync_content(file_content)
        return response, 200
    except Exception as e:
        return str(e), 500
    

@app.route("/get", methods = ['POST'])
def get_response():
    session_id = request.json['session_id']
    message = request.json['msg']
    session_attributes = request.json['session_attributes']
    prompt_attributes = request.json['prompt_attributes']
    
    response_text = bot_client.send_message(message, session_id, session_attributes, prompt_attributes)
    response = {'msg': response_text}
    return response, 200

if __name__ == "__main__":
    from waitress import serve
    import os
    print(os.environ['APP_HOST'])
    serve(app, host="0.0.0.0", port="5001")
