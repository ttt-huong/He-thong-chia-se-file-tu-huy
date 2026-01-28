"""
Test with Flask debug enabled to see actual error
"""
import os
os.environ['FLASK_ENV'] = 'development'
os.environ['DEBUG'] = '1'

from src.gateway.app import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
