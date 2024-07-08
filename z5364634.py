#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
COMP9321 24T1 Assignment 2
Data publication as a RESTful service API

Getting Started
---------------

1. You MUST rename this file according to your zID, e.g., z1234567.py.

2. To ensure your submission can be marked correctly, you're strongly encouraged
   to create a new virtual environment for this assignment.  Please see the
   instructions in the assignment 1 specification to create and activate a
   virtual environment.

3. Once you have activated your virtual environment, you need to install the
   following, required packages:

   pip install python-dotenv==1.0.1
   pip install google-generativeai==0.4.1

   You may also use any of the packages we've used in the weekly labs.
   The most likely ones you'll want to install are:

   pip install flask==3.0.2
   pip install flask_restx==1.3.0
   pip install requests==2.31.0

4. Create a file called `.env` in the same directory as this file.  This file
   will contain the Google API key you generatea in the next step.

5. Go to the following page, click on the link to "Get an API key", and follow
   the instructions to generate an API key:

   https://ai.google.dev/tutorials/python_quickstart

6. Add the following line to your `.env` file, replacing `your-api-key` with
   the API key you generated, and save the file:

   GOOGLE_API_KEY=your-api-key

7. You can now start implementing your solution. You are free to edit this file how you like, but keep it readable
   such that a marker can read and understand your code if necessary for partial marks.

Submission
----------

You need to submit this Python file and a `requirements.txt` file.

The `requirements.txt` file should list all the Python packages your code relies
on, and their versions.  You can generate this file by running the following
command while your virtual environment is active:

pip freeze > requirements.txt

You can submit the two files using the following command when connected to CSE,
and assuming the files are in the current directory (remember to replace `zid`
with your actual zID, i.e. the name of this file after renaming it):

give cs9321 assign2 zid.py requirements.txt

You can also submit through WebCMS3, using the tab at the top of the assignment
page.

"""

# You can import more modules from the standard library here if you need them
# (which you will, e.g. sqlite3).
import os
import datetime
import requests
import random
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_restx import Resource, Api
from flask_sqlalchemy import SQLAlchemy

# You can import more third-party packages here if you need them, provided
# that they've been used in the weekly labs, or specified in this assignment,
# and their versions match.
from dotenv import load_dotenv          # Needed to load the environment variables from the .env file
import google.generativeai as genai     # Needed to access the Generative AI API


studentid = Path(__file__).stem         # Will capture your zID from the filename.
db_file   = f"{studentid}.db"           # Use this variable when referencing the SQLite database file.
txt_file  = f"{studentid}.txt"          # Use this variable when referencing the txt file for Q7.


# Load the environment variables from the .env file
load_dotenv()

# Configure the API key
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# Create a Gemini Pro model
gemini = genai.GenerativeModel('gemini-pro')

# set up environment
app = Flask(__name__)
current_directory = os.getcwd()
database_file = os.path.join(current_directory, db_file)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_file}'
db = SQLAlchemy(app)
api = Api(app)

host = '127.0.0.1:5000'
# define database
class STOP(db.Model):
    __tablename__ = 'stops'
    # stop id
    stop_id = db.Column(db.Integer, primary_key=True)
    # last updated time
    last_updated = db.Column(db.String(100), default=datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S'))
    # links
    _links = db.Column('links', db.PickleType)
    # name
    name = db.Column(db.String(500))
    # latitude
    latitude = db.Column(db.Float)
    # longitude
    longitude = db.Column(db.Float)
    # next_departure
    next_departure = db.Column(db.String(500))
    
    def __init__(self, stop_id, last_updated,_links=None, name=None, latitude=None, longitude=None, next_departure=None):
        self.stop_id = stop_id
        self.last_updated = last_updated
        self._links = _links if _links is not None else {'self': None, 'prev': None, 'next': None}
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.next_departure = next_departure
    
ns = api.namespace('stops', desciption = 'Stop Operation')

@ns.route('/')
class stopList(Resource):
    @ns.param(name='query', description='query string')
    @api.doc(description='upload stops needed')
    @api.response(200, 'Success')
    @api.response(201, 'Created')
    @api.response(400, 'Bad Request')
    @api.response(404, 'Not Found')
    @api.response(503, 'Service Unavailable')
    # PUT method
    def put(self):
        query = request.args.get('query')
        if not query:
            api.abort(400, 'Query Should NOT BE Empty!')

        # access information of stops
        db_response = requests.get(f'https://v6.db.transport.rest/locations?query={query}&results=5')
        stops = db_response.json()
        updated_stops = []
        existed_stops = []
        for stop in stops:
            if stop['type'] == 'stop':
                existed_stop = STOP.query.filter_by(stop_id=stop['id']).first()

                if existed_stop:
                    existed_stop.last_updated = datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
                    updated_stops.append(existed_stop)
                    existed_stops.append(existed_stop)


                else:
                    new_stop = STOP(
                        stop_id = stop['id'],
                        last_updated = datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S'),
                        _links = {'self': f'http://{host}/stops/{stop["id"]}', 'prev': None, 'next': None},
                        name = stop['name'],
                        latitude = stop['location']['latitude'],
                        longitude = stop['location']['longitude'],
                    )
                    db.session.add(new_stop)
                    updated_stops.append(new_stop)


        for stop in STOP.query.all():
            prev = STOP.query.filter(STOP.stop_id < stop.stop_id).order_by(STOP.stop_id.desc()).first()
            next = STOP.query.filter(STOP.stop_id > stop.stop_id).order_by(STOP.stop_id.asc()).first()
            if prev and next:
                STOP.query.filter_by(stop_id = stop.stop_id).update({'_links':\
                                                                     {'self': f'http://{host}/stops/{stop.stop_id}',\
                                                                       'prev': prev._links['self'],\
                                                                        'next': next._links['self']}})
            else:
                if next is None:
                   STOP.query.filter_by(stop_id = stop.stop_id).update({'_links':\
                                                                     {'self': f'http://{host}/stops/{stop.stop_id}',\
                                                                       'prev': prev._links['self'],\
                                                                        'next': None}})
                if prev is None:
                    STOP.query.filter_by(stop_id = stop.stop_id).update({'_links':\
                                                                     {'self': f'http://{host}/stops/{stop.stop_id}',\
                                                                       'prev': None,\
                                                                        'next': next._links['self']}})
            db.session.commit()

        updated_stops = sorted(updated_stops, key=lambda x:x.stop_id)

        # return status code
        if len(updated_stops) != len(existed_stops):
            for i in range(len(updated_stops)):
                updated_stops[i] = {
                    'stop_id': updated_stops[i].stop_id,
                    'last_updated': updated_stops[i].last_updated,
                    '_links': {
                      'self': {
                        'href': updated_stops[i]._links['self']
                        }
                    }
                }
            return updated_stops, 201
        else:
            return {'message':'no stops updated'}, 200


query_model = api.model('UpdateModel', {})
@ns.route('/<int:id>')
class StopDetail(Resource):
    @api.doc(description='Get Stops Detailed Information')
    @api.response(200, 'Success')
    @api.response(400, 'Bad Request')
    @api.response(404, 'Not Found')
    @api.response(503,'Service Unavailable')
    @ns.param(name='include', description='include parameter')
    def get(self, id):
        stop = STOP.query.get(id)

        if not stop:
            api.abort(404, 'not found')

        basic_data = {
            'stop_id':stop.stop_id,
            '_links':{
                'self':{
                    'href': f'http://{host}/stops/{id}'
                }
            }
        }

        if stop._links['prev']:
            basic_data['_links']['prev'] = {'href' : stop._links['prev']}
        
        if stop._links['next']:
            basic_data['_links']['next'] = {'href': stop._links['next']}
        
        response = requests.get(f'https://v6.db.transport.rest/stops/{id}/departures?when=now&duration=120')        
        if response.ok:
            departures = response.json()['departures']
            next_departure = departures[0]
            if next_departure['platform'] and next_departure['direction']:
                basic_data['next_departure'] = f'platform {next_departure['platform']} towards {next_departure['direction']}'
                stop.next_departure = basic_data['next_departure']
                stop.last_updated = datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
                db.session.commit()
            else:
                api.abort(404, message='Not Found')
        else:
            api.abort(404, message='Not Found')
        
        include = request.args.get('include')
        if include is None:
            basic_data['last_updated'] = stop.last_updated
            basic_data['name'] = stop.name
            basic_data['latitude'] = stop.latitude
            basic_data['longitude'] = stop.longitude

            return basic_data, 200
        include_list = include.split(',') if include else []
        
        if include_list:
            for field in include_list:
                basic_data[f'{field}'] = getattr(stop, field)

        return basic_data, 200
        
    
    @api.doc(description='Delete Useless Stop')
    @api.response(200, 'Success')
    @api.response(400, 'Bad Request')
    @api.response(404, 'Not Found')
    def delete(self, id):
        
        stop = STOP.query.get(id)
        if stop is None:
            return {'message' : f"The stop_id {id} was not found in the database.", "stop_id": f'{id}'}, 404
        
        else:
            prev_link = stop._links['prev']
            next_link = stop._links['next']
            if prev_link is None:
                next_id = int(next_link.split('/')[-1])
                next_stop = STOP.query.get(next_id)
                updated_links = {
                    'self': next_stop._links['self'],
                    'prev': None,
                    'next': next_stop._links['next']
                }
                STOP.query.filter_by(stop_id=next_id).update({'_links': updated_links})
            
            if next_link is None:
                prev_id = int(prev_link.split('/')[-1])
                prev_stop = STOP.query.get(prev_id)
                updated_links = {
                    'self': prev_stop._links['self'],
                    'prev': prev_stop._links['prev'],
                    'next': None
                }
                STOP.query.filter_by(stop_id=prev_id).update({'_links': updated_links})
            
            if prev_link and next_link:
                next_id = int(next_link.split('/')[-1])
                next_stop = STOP.query.get(next_id)
                updated_links_1 = {
                    'self': next_stop._links['self'],
                    'prev': prev_link,
                    'next': next_stop._links['next']
                }
                STOP.query.filter_by(stop_id=next_id).update({'_links': updated_links_1})
                
                prev_id = int(prev_link.split('/')[-1])
                prev_stop = STOP.query.get(prev_id)
                updated_links_2 = {
                    'self': next_stop._links['self'],
                    'prev': prev_stop._links['prev'],
                    'next': next_link
                }
                STOP.query.filter_by(stop_id=prev_id).update({'_links': updated_links_2})

            db.session.delete(stop)
            
            db.session.commit()

            return {'message' : f'The stop_id {id} was removed from the database.', "stop_id": f'{id}'}, 200

    
    @api.doc(description='Update Information of Stop')
    @api.response(200, 'Success')
    @api.response(400, 'Bad Request')
    @api.response(404, 'Not Found')
    # @ns.expect(query_model, validate=False)
    def patch(self, id):
        updatable_fields = ['name', 'next_departure', 'latitude', 'longitude', 'last_updated']
        data = request.json

        if not all(data.values()):
            return {'message': 'Empty fields are not allowed'}, 400
        if '_links' in data or 'stop_id' in data:
            return {'message': '"_links" and "stop_id" parameters are not permitted'}, 400
        
        stop = STOP.query.get(id)
        if stop is None:
            return {'message' : f"The stop_id {id} was not found in the database."}, 404

        output = {
            'stop_id': stop.stop_id,
            '_links': {
                'self': {
                    'href': stop._links['self']
                }
            }
        }

        if 'last_updated' in data:
            try:
                datetime.datetime.strptime(data['last_updated'], '%Y-%m-%d-%H:%M:%S')
            except ValueError:
                return {'message': 'Invalid format for last_updated field. Use yyyy-mm-dd-hh:mm:ss'}, 400
        else:
            output['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S')

        for field, value in data.items():
            if field not in updatable_fields:
                return {'message': 'invalid field name'}, 400
            STOP.query.filter_by(stop_id=id).update({field:value})
            db.session.commit()

        return output, 200




@api.route('/operator-profiles/<int:id>')
class OperatorProfileResource(Resource):
    @api.doc(description='Generate Operator Profiles of Stop')
    @api.response(200, 'Success')
    @api.response(400, 'Bad Request')
    @api.response(404, 'Not Found')
    @api.response(503, 'Service Unavailable')
    def get(self, id):
        stop = STOP.query.get(id)
        if stop is None:
            return {'message': 'Operator profile not found'}, 404

        operator_names = set()

        output = {
            'stop_id': id,
            'profiles': []
        }

        response = requests.get(f'https://v6.db.transport.rest/stops/{id}/departures?when=now&duration=90')
        if response.ok:
            depatures = response.json()['departures']
            
            for trip in depatures:
                operator_names.add(trip['line']['operator']['name'])
                if len(operator_names) == 5:
                    break
            
            for operator_name in operator_names:
                question = f"Give me some information about {operator_name}"
                res = gemini.generate_content(question)
                output['profiles'].append(res.text)

        return output, 200
             
            
@api.route('/guide')
class generateGuide(Resource):
    @api.doc(description='Create a Tourism Guide')
    @api.response(200, 'Success')
    @api.response(400, 'Bad Request')
    @api.response(503, 'Service Unavailable')
    def get(self):
        stops = STOP.query.all()
        if len(stops) < 2:
            return {'message' : 'There are less 2 stops in the database'}, 400
        
        random_integers = random.sample(range(len(stops)), 2)
        source = stops[random_integers[0]]
        destination = stops[random_integers[1]]

        response = requests.get(f'https://v6.db.transport.rest/journeys?from={source.stop_id}&to={destination.stop_id}')
        if response.ok:
            file_path = f'{studentid}.txt'
            partition_line = ['\n','-------------------------------------------------------------------\n','\n']
            
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(f'Interests of {source.name}:\n')
                question1 = f'Give me interests of {source.name}'
                res1 = gemini.generate_content(question1).text
                file.writelines(res1)
                file.writelines(partition_line)
                
                file.writelines(f'Interests of {destination.name}:\n')
                question2 = f'Give me interests of {destination.name}'
                res2 = gemini.generate_content(question2).text
                file.writelines(res2)
                file.writelines(partition_line)
                
                file.write('Here is the extra information:\n')
                question3 = f'Give me weather of {source.name} and {destination.name} for the next 5 days'
                res3 = gemini.generate_content(question3).text
                file.writelines(res3)
            
            return send_file(file_path, as_attachment=True)
        
        else:
            return {'message' : 'There is no path between source and destination'}, 400
                
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
