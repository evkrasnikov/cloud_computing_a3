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
BUCKET_TRANSLATE = 'krasniko-a3-translate'
BUCKET_MP3_URL = "https://krasniko-a3-mp3.s3.amazonaws.com"

LGN_REQ_TXT = "Username must contain 6 - 100 symbols all of which must be alphanumeric characters"
PSWD_REQ_TXT = "Password must also contain 6 - 100 symbols all of which must be alphanumeric or _*&^%$#@!-+="

lang_code_mapping = {
        "en": "English",
        "es": "Spanish",
        "it": "Italian",
        "fr": "French"
        }

dynamodb = boto3.resource('dynamodb')
s3 = boto3.resource('s3')


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
    '''Displays the upload form and populates the form with presigned URL 
    for direct POST request to S3'''
    usr = session.get('username')
    #print(url_for("test_redirect", _external=True), file=sys.stderr)
    object_name = "{}/{}".format(usr, "${filename}")
    presigned = create_presigned_post(BUCKET_MP3, object_name, {"success_action_redirect": "http://www.google.com/"}, [["starts-with", "$success_action_redirect", ""]])
    
    #print(presigned, file=sys.stdout)
    #error = session.get("error")
    #session.pop("error", None)
    return render_template('upload_form.html', presigned=presigned)


@webapp.route('/test_redirect')
def test_redirect():
    '''This function is invoked after S3 redirect. It creates a record in the database,
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
    #print(resp)
    #print(src_lang, dst_lang, file_name, file=sys.stderr)
    session["message"] = "File successfully uploaded"

    # also need to make uploaded mp3 file public
    s3.ObjectAcl(BUCKET_MP3, s3_key).put(ACL='public-read')

    return redirect(url_for("dashboard"))


@webapp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    '''Displays a table of all file uploaded by the user'''
    error = session.get("error")
    session.pop("error", None)
    message = session.get("message")
    session.pop("message", None)

    usr = session.get('username')

    # list all files that are owned by the user
    key_condition = boto3.dynamodb.conditions.Key('user')
    table = dynamodb.Table("files")
    response = table.query(
        #IndexName="user",
        KeyConditionExpression=key_condition.eq(usr)
    )
    print(response, file=sys.stderr)
    items = []
    if "Items" in response:
        items = response["Items"]
    
    return render_template('dashboard.html', username=usr, items=items, error=error, message=message)


def get_text_from_s3_file(bucket, key):
    """Downloads a text file from S3 and returns the content"""
    tmp_path = "/tmp/temp_a3.txt"
    s3.meta.client.download_file(bucket, key, tmp_path)
    with open(tmp_path, "r") as f:
        text = f.read()
    return text

def generate_json(text_src, text_dst, text_timings):
    """Generate json from two textfiles and a timing file"""
    sentences_src = text_src.split("[1]")
    sentences_dst = text_dst.split("[1]")
    timings = text_timings.split(",")
    data = []
    
    for src, dst, timing in zip(sentences_src, sentences_dst, timings):
        if len(timing) == 0 or len(src) == 0 or len(dst) == 0:
            continue
        print(dst, file=sys.stderr)
        start_time, end_time = timing.split("-")
        elem = {"start": start_time, "end": end_time, "text_src": src, "text_dst": dst}
        data.append(elem)
    print(len(sentences_dst), len(sentences_src), len(timings), file=sys.stderr)

    return data

def generate_json_updated(text_src, text_dst, text_timings):
    # split timing file 
    # text_src.find(anchor)
    timings = text_timings.split(",")
    num_sentences = len(timings)
    last_sentence_src_pos = 0
    last_sentence_dst_pos = 0
    sentence_start_time = 0
    #sentence_end_time = 0
    new_sentence = True
    data = []
    for i in range(num_sentences):
        if timings[i] == "":
            continue

        anchor = "[{}]".format(i)
        anchor_pos_src = text_src.find(anchor)
        anchor_pos_dst = text_dst.find(anchor)
        start_time, end_time = timings[i].split("-")
        #print(text_src.find("[3]"))
        if anchor_pos_src == -1 or anchor_pos_dst == -1:
            print("coudnt find anchor ", anchor, anchor_pos_src, anchor_pos_dst)
            if new_sentence:
                sentence_start_time = start_time
                new_sentence = False
        else:
            sentence_src = text_src[last_sentence_src_pos: anchor_pos_src]
            sentence_dst = text_dst[last_sentence_dst_pos: anchor_pos_dst]
            last_sentence_src_pos = anchor_pos_src
            last_sentence_dst_pos = anchor_pos_dst
            if new_sentence:
                sentence_start_time = start_time

            #sentence_end_time = end_time
            new_sentence = True
            elem = {"start": sentence_start_time, "end": end_time, "text_src": sentence_src, "text_dst": sentence_dst}
            data.append(elem)
    print(data, file=sys.stderr)
    return data


@webapp.route('/view/<filename>', methods=['GET'])
@login_required
def view(filename):
    """Displays the  """
    usr = session.get('username')
    filename_noext = filename.split(".")[0]

    # deteremine which language file need to be downloaded
    table = dynamodb.Table("files")
    resp = table.get_item(
        Key={"user": usr, "filename": filename}
    )
    #print(resp, file=sys.stderr)
    if "Item" not in resp:
        return "something went wrong"
    else:
        srclang = resp["Item"]["srclang"]
        dstlang = resp["Item"]["dstlang"]
    
    item = resp["Item"]
    item["srclang"] = lang_code_mapping[item["srclang"]]
    item["dstlang"] = lang_code_mapping[item["dstlang"]]

    # get the url for mp3 file
    mp3_url = "{}/{}/{}".format(BUCKET_MP3_URL, usr, filename)

    # download texts for the source, destination languages and timings file
    src_object_name = "{}/{}.{}".format(usr, filename_noext, srclang)
    dst_object_name = "{}/{}.{}".format(usr, filename_noext, dstlang)
    timings_object_name = "{}/{}.time".format(usr, filename_noext)
    print(src_object_name, timings_object_name, file=sys.stderr)

    src_text = get_text_from_s3_file(BUCKET_TRANSLATE, src_object_name)
    dst_text = get_text_from_s3_file(BUCKET_TRANSLATE, dst_object_name)
    timings_text = get_text_from_s3_file(BUCKET_TRANSLATE, timings_object_name)
    
    #print(src_text, dst_text, timings_text, file=sys.stderr)
    
    # create json thing needed for javascript
    #data = generate_json(src_text, dst_text, timings_text)
    data = generate_json_updated(src_text, dst_text, timings_text)
    
    
    return render_template('view.html', data=data, mp3_url=mp3_url, item=item)

@webapp.route('/logout', methods=['GET', 'POST'])
def logout():
    '''Logs out the users by clearning his session object'''
    session.clear()
    return redirect(url_for('login'))
