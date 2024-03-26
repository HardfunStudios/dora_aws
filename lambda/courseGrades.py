import requests
import sys
import os 

sys.path.insert(0, './lib')

import moodle_api

def find_parameter_value(parameters, name):
  for parameter in parameters:
    if parameter['name'] == name:
      return parameter['value']
  return None

def get_moodle_course_grades(event, context):
  moodle_api.URL = os.environ.get('MOODLE_URL')
  moodle_api.KEY = os.environ.get('MOODLE_WS_KEY')
  
  properties = event['requestBody']["content"]["application/json"]["properties"]
  
  courseid = find_parameter_value(properties, 'courseid')
  userid = find_parameter_value(properties, 'userid')

  grades = moodle_api.call('local_chatbot_dora_get_user_grade_for_course', courseid=courseid, userid=userid)
  response_body = grades
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
