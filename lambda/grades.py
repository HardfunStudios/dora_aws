import sys
sys.path.insert(0, './lib')

import moodle_api
import json
import requests

def get_moodle_user_grades_handler(event, context):
  moodle_api.URL = 'https://moodlefte.hardfunstudios.com/'
  moodle_api.KEY = 'db836220c1667548917bde73c8e4a4f7'

  user = moodle_api.call('core_user_get_users_by_field', field='username', values=[event['username']])
  
  if len(user) == 0:
    return {
      "statusCode": 404,
      "headers": {
        "Content-Type": "application/json"
      },
      "body": "User not found"
    } 
  else:
    user = user[0]

  raw_grades = moodle_api.call('gradereport_overview_get_course_grades', userid=user['id'])
  grades = []
  for raw_grade in raw_grades['grades']:
    grades.append({
      'grade': raw_grade['grade'],
      'course_name': moodle_api.call('core_course_get_courses_by_field', field='id', value=215)['courses'][0]['fullname']
    })

  return {
    "statusCode": 200,
    "headers": {
      "Content-Type": "application/json"
    },
    "body": grades
  }
