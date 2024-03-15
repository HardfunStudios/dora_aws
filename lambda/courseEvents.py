import sys
sys.path.insert(0, './lib')

import moodle_api
import json
import requests

def get_moodle_course_pending_activities(event, context):
  moodle_api.URL = 'https://moodlefte.hardfunstudios.com/'
  moodle_api.KEY = 'db836220c1667548917bde73c8e4a4f7'
  
  properties = event['requestBody']["content"]["application/json"]["properties"]
  courseid = int(properties[0]['value'])
  activities = moodle_api.call('local_chatbot_dora_get_user_pending_activities_for_course', courseid=courseid)

  if len(activities) == 0:
    response_body = {"message": "No pending activities."}
    status_code = 200
  else:
    response_body = activities
    status_code = 200
    
    action_response = {
        'actionGroup': event['actionGroup'],
        'apiPath': event['apiPath'],
        'httpMethod': event['httpMethod'],
        'httpStatusCode': status_code,
        'responseBody': response_body
    }
    
    session_attributes = event['sessionAttributes']
    prompt_session_attributes = event['promptSessionAttributes']
    
    api_response = {
        'messageVersion': '1.0', 
        'response': action_response,
        'sessionAttributes': session_attributes,
        'promptSessionAttributes': prompt_session_attributes
    }
        
    return api_response
