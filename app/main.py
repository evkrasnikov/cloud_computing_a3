'''Module contains all views and functions for database access '''
import os, sys
from flask import render_template, url_for, redirect, request, session, g, jsonify

from werkzeug.utils import secure_filename
from . import webapp
from .utils import password_hash, gen_salt, valid_password, valid_login_name, valid_file_ext
from .utils import upload_file_s3, set_file_public_read_s3

import functools
import boto3
from botocore.exceptions import ClientError

#files table will hav the following attributes
# user, filename, srclang, dstlang, timing_file, src_file, dst_file
# timing_file, src_file, dst_file will be updated only when they become available

def login_required(func):
    '''A decorator for URL endpoints that should be accessed
    only by logged in users. Whether user is logged in or not
    is determined by presence of "username" key in session.
    If user is not logged in, he is redirected to login page
    '''
    @functools.wraps(func)
    def wrapper_func(*args, **kwargs):
        if session.get("auth") is None:
            session["error"] = "You need to login to access that part of website"
            return redirect(url_for('login'))

        value = func(*args, **kwargs)
        return value
    return wrapper_func


@webapp.teardown_appcontext
def teardown_db(exception):
    '''Closes connection to mysql database'''
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


ADD_USER = 'INSERT INTO users (name, salt, hash_pass) VALUES (%s, %s, %s)'
GET_USER = "SELECT * FROM users WHERE name = %s"
ADD_IMG = "INSERT INTO files (name, users_name) VALUES (%s, %s)"
GET_LAST_IMG_ID = "SELECT MAX(id) FROM files WHERE users_name = %s"
GET_USER_IMGS = "SELECT id, name FROM files WHERE users_name = %s"
GET_IMG_BY_ID = "SELECT users_name, name FROM files WHERE id = %s"
AWS_BUCKET_URL = "https://krasniko-ece1779-a2.s3.amazonaws.com"
AWS_BUCKET_NAME = "krasniko-ece1779-a2"

BUCKET_MP3 = 'krasniko-a3-mp3'

LGN_REQ_TXT = "Username must contain 6 - 100 symbols all of which must be alphanumeric characters"
PSWD_REQ_TXT = "Password must also contain 6 - 100 symbols all of which must be alphanumeric or _*&^%$#@!-+="

dynamodb = boto3.resource('dynamodb')


def create_presigned_post(bucket_name, object_name,
                          fields=None, conditions=None, expiration=3600):
    """Generate a presigned URL S3 POST request to upload a file

    :param bucket_name: string
    :param object_name: string
    :param fields: Dictionary of prefilled form fields
    :param conditions: List of conditions to include in the policy
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Dictionary with the following keys:
        url: URL to post to
        fields: Dictionary of form fields and values to submit with the POST
    :return: None if error.
    """

    # Generate a presigned S3 POST URL
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_post(bucket_name,
                                                     object_name,
                                                     Fields=fields,
                                                     Conditions=conditions,
                                                     ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL and required fields
    return response


@webapp.route('/')
@webapp.route('/login', methods=['GET'])
def login():
    '''Starting endpoint. Returns a login form to fill'''
    
    uname = session.get("username")
    error = session.get("error")
    message = session.get("message")
    session.pop("error", None)
    session.pop("message", None)
    if session.get("auth"):
        return redirect(url_for('dashboard'))

    return render_template('login_form.html', uname=uname, error=error, message=message)


@webapp.route('/login_submit', methods=['POST'])
def login_submit():
    '''Reads the data from the submitted login form. Authenticates the 
    user if credentials match the ones stored in the DB. If no match,
    redirects back to login page
    '''

    if session.get("auth"):
        return redirect(url_for('dashboard'))

    pswd = request.form['password']
    lgn = request.form['username']
    if lgn is None or pswd is None:
        session["error"] = "Wrong form. Password or username field was not found"
        return redirect(url_for('login'))
    session['username'] = lgn

    if valid_login_name(lgn) and valid_password(pswd):
        # Access databse and check that user exists
        table = dynamodb.Table("auth")
        resp = table.get_item(
            Key={"login_name": lgn}
        )

        if "Item" not in resp:
            session["error"] = "User doesn't exist"
            return redirect(url_for('login'))
        item = resp["Item"]
        
        if "salt" not in item or "hash_pass" not in item:
            session["error"] = "Problem with database, couldn't find password"
            return redirect(url_for('login'))

        # Make sure that password matches one stored in database
        received_pass = password_hash(pswd, item['salt'])
        if item['hash_pass'] != received_pass:
            session["error"] = "Wrong password"
            return redirect(url_for('login'))
    else:
        session["error"] = "Invalid login or password"
        return redirect(url_for('login'))

    session['auth'] = lgn
    return redirect(url_for('dashboard'))


@webapp.route('/register', methods=['GET'])
def register():
    '''Displays the registration form for the user to fill'''
    uname = session.get("username")
    error = session.get("error")
    session.pop("error", None)

    if session.get("auth"):
        return redirect(url_for('dashboard'))
    
    return render_template('register_form.html', uname=uname, error=error)


@webapp.route('/register_submit', methods=['POST'])
def register_submit():
    '''Reads the information provided in registration form. Creates a new
    user if information is valid. Redirects back to registration page, if
    some of the information is not valid.
    '''

    if session.get("auth"):
        return redirect(url_for('dashboard'))
    
    pswd = request.form['password']
    lgn = request.form['username']
    if lgn is None or pswd is None:
        session["error"] = "Wrong form. Password or username field was not found"
        return redirect(url_for('register'))
    session['username'] = lgn
    
    #session['username'] = lgn
    if valid_login_name(lgn) and valid_password(pswd):
        # Make sure that provided username doesn't exist
        table = dynamodb.Table("auth")
        resp = table.get_item(
            Key={"login_name": lgn}
        )

        if "Item" in resp:
            session["error"] = "User already exists"
            return redirect(url_for('register'))

    else:
        session["error"] = "Invalid login or password"
        return redirect(url_for('register'))

    # Add the users credentials to database
    salt = gen_salt()
    hashed_pass = password_hash(pswd, salt)
    
    table = dynamodb.Table("auth")
    resp = table.put_item(
        Item={
            'login_name': lgn,
            'salt': salt,
            'hash_pass': hashed_pass
        }
    )
    session["message"] = "User successfully registered"

    return redirect(url_for('login'))


@webapp.route('/upload')
def upload():
    '''Displays the upload form'''
    usr = session.get('username')
    print(url_for("test_redirect", _external=True), file=sys.stderr)
    object_name = "{}/{}".format(usr, "${filename}")
    presigned = create_presigned_post(BUCKET_MP3, object_name, {"success_action_redirect": "http://www.google.com/"}, [["starts-with", "$success_action_redirect", ""]])
    print(presigned, file=sys.stdout)
    error = session.get("error")
    session.pop("error", None)
    return render_template('upload_form.html', error=error, presigned=presigned)


@webapp.route('/test_redirect')
def test_redirect():
    '''need to create a record in the database,
    lambda will then act on the record and will know which language
    to translate from and to'''

    src_lang = request.args.get('src')
    dst_lang = request.args.get('dst')
    s3_key = request.args.get('key')
    usr = session.get('username')

    # separate filename and folder name
    folder_name, file_name = s3_key.split('/')
    
    # now populate the table 
    table = dynamodb.Table("files")
    resp = table.put_item(
        Item={
            'user': usr,
            'filename': file_name,
            'srclang': src_lang,
            'dstlang': dst_lang
        }
    )
    print(resp)
    print(src_lang, dst_lang, file_name, file=sys.stderr)
    session["message"] = "File successfully uploaded"

    return redirect(url_for("dashboard"))

    # '''Displays the upload form'''
    # usr = session.get('username')

    # object_name = "{}/{}".format(usr, "${filename}")
    # presigned = create_presigned_post(BUCKET_MP3, object_name)
    # print(presigned, file=sys.stdout)
    # error = session.get("error")
    # session.pop("error", None)
    # return render_template('upload_form.html', error=error, presigned=presigned)


@webapp.route('/upload_submit', methods=['POST'])
def upload_submit():
    '''Read and save the file submitted through the upload form.
    Also creates thumbnail and runs object detection
    '''

    if 'file' not in request.files:
        session["error"] = 'Wrong form, no file part'
        return redirect(url_for("upload"))
    file = request.files['file']
    
    if file.filename == '':
        session["error"] = 'File not selected'
        return redirect(url_for('upload'))
    
    if file: #and valid_file_ext(file.filename):
        # Update database and get the id value of the file
        fname = secure_filename(file.filename)
        # try:
        #     img_id = add_file_db(fname, session['username'])
        # except mysql.connector.Error as error:
        #     session["error"] = "Problem accessing database, please try again"
        #     return redirect(url_for('upload'))
        s3 = boto3.client('s3')
        s3.upload_fileobj(file, AWS_BUCKET_NAME, fname)

    else:
        session["error"] = 'Unsupported image format'
        return redirect(url_for('upload'))
    
    return redirect(url_for('upload'))


@webapp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    '''Displays thumbnails of all photos uploaded by the user'''
    error = session.get("error")
    session.pop("error", None)

    usr = session.get('username')
    # cnx = get_db()
    # # Get all images uploaded by the user
    # try:
    #     cursor = cnx.cursor()
    #     cursor.execute(GET_USER_IMGS, (usr,))
    # except mysql.connector.Error as error:
    #     session["error"] = "Problem accessing database, please try again"
    
    # imgs = [(id, url_for("static", filename="tmb/{}_{}".format(id, name)), name) for id, name in cursor]
    
    return render_template('dashboard.html', username=usr, stuff=[], error=error)

@webapp.route('/logout', methods=['GET', 'POST'])
def logout():
    '''Logs out the users by clearning his session object'''
    session.clear()
    return redirect(url_for('login'))
