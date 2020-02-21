# -*- coding: utf-8 -*-

import os
import sys
import psycopg2

import configparser

from flask import Flask, render_template, flash, redirect, url_for, session, logging, request, jsonify
from flask_cors import CORS

# from wtforms import Form, StringField, TextAreaField, PasswordField, validators
# from passlib.hash import sha256_crypt
from functools import wraps
import requests

from flask_restful import Resource, Api, reqparse
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    get_jwt_identity, decode_token
)

from models.tiles_model import Tiles

parser = reqparse.RequestParser()

app = Flask(__name__)
api = Api(app)
cors = CORS(app)

config = configparser.ConfigParser()

dirname = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(dirname, '.config.ini')
config.read(config_path)

try:
    secret_key = config.get('secret', 'key')

    app.config['JWT_SECRET_KEY'] = secret_key
    jwt = JWTManager(app)

    host = config.get('dbsettings', 'db_host')
    user = config.get('dbsettings', 'db_user')
    passwd = config.get('dbsettings', 'db_passwd')
    dbname = config.get('dbsettings', 'db_dbname')
    db = psycopg2.connect(database=dbname, user=user,
                          password=passwd, host=host)

    base_url = config.get('env', 'base_url')
    vtiles_url = config.get('env', 'vtiles_url')
    vitles_cache = config.get('env', 'vitles_cache')
    download_uri = config.get('env', 'download_uri')

except Exception as err:
    print(str(err), ' could not connect to db')
    sys.exit()


@app.route('/')
def render_static():
    return render_template('index.html')


@app.route('/tiles')
def render_static_home():
    return render_template('index.html')

api.add_resource(Tiles, '/tiles/<composition>/<sensor>/<product_date>/<int:z>/<int:x>/<int:y>.png',
                 resource_class_kwargs={'db': db})


if __name__ == '__main__':
    app.secret_key = secret_key
    app.run(debug=True, port=5005)
