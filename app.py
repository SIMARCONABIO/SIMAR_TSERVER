# -*- coding: utf-8 -*-
'''
http://localhost:5005/tiles/nsst/ghrsst/2020-01-01/wmts/nsst/webmercator/5/5/15.png

http://localhost/cgi-bin/mapserv?height=1184&width=1184&styles=&srs=EPSG%3A3857&request=GetMap&map=/mnt/simar-images/NOAA/NOAA-M-NSST/crw_climatology_1km_20170228_agu.map&version=1.1.1&transparent=true&bbox=-15419488.841912035,-391357.58482010313,-9627396.586574519,5400734.670517415&format=image/png&layers=raster&service=WMS
'''
import os
import sys
import psycopg2

import configparser

from flask import Flask, render_template, flash, redirect, url_for, session, logging, request, \
    jsonify, send_from_directory
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

from models.home_model import Root, ApiRoot
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

    base_dir = config.get('env', 'base_dir')
    mapserver_bin = config.get('env', 'mapserver_bin')
    basemap_map = config.get('env', 'basemap_map')

except Exception as err:
    print(str(err), ' could not connect to db')
    sys.exit()


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


api.add_resource(Root, '/')
api.add_resource(ApiRoot, '/api')

api.add_resource(Tiles, '/tiles/<composition>/<sensor>/<product_date>/<stype>/<product>/<tilematrix>/<int:z>/<int:x>/<int:y>.png',
                 '/tiles/<composition>/<sensor>/<product_date>/<stype>',
                 resource_class_kwargs={'db': db, 'base_dir': base_dir, 'mapserver_bin': mapserver_bin, 'basemap_map': basemap_map})


if __name__ == '__main__':
    app.secret_key = secret_key
    app.run(host='0.0.0.0', debug=True, port=5005)
