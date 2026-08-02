import os

class Config:
    SECRET_KEY = 'your-secret-key-change-this-later'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost/complaint_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
