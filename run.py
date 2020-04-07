#from user_app import webapp
#webapp.run(host='localhost',port='5000', debug=True)

import sys
#import manager_app
import app
if __name__ == "__main__":
    app.webapp.run(host='0.0.0.0', port='5001')#debug=True)

