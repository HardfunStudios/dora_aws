import sys
sys.path.insert(0, './lib')

import moodle_api
import json
import requests

def get_moodle_user_grades_handler(event, context):
  moodle_api.URL = 'https://moodlefte.hardfunstudios.com/'
  moodle_api.KEY = 'db836220c1667548917bde73c8e4a4f7'
  
  properties = event['requestBody']["content"]["application/json"]["properties"]
  username = properties[0]['value']
  user = moodle_api.call('core_user_get_users_by_field', field='username', values=[username])
  
  if len(user) == 0:
    response_body = "Username invalid."
    status_code = 404
  else:
    user = user[0]

    raw_grades = moodle_api.call('gradereport_overview_get_course_grades', userid=user['id'])
    grades = []
    
    for raw_grade in raw_grades['grades']:
      grades.append({
        'grade': raw_grade['grade'],
        'course_name': moodle_api.call('core_course_get_courses_by_field', field='id', value=215)['courses'][0]['fullname']
      })
  
      response_body = {
          'application/json': {
              'body': grades
          }
      }
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
