import sys
sys.path.insert(0, './lib')

import moodle_api
import json
import requests

# def get_moodle_user_grades_handler(event, context):
moodle_api.URL = 'https://moodlefte.hardfunstudios.com/'
moodle_api.KEY = 'd546319a7268acb6a5788d5f49564565'


user = moodle_api.User(username='02408118018')
user = user.get_by_field()
courses = moodle_api.CourseList()
enrollments = user.enrolments(courses)
print(courses)

