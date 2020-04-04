'''Contains utility functions used throughout the app'''

import hashlib
import random
import re
import boto3

ALLOWED_EXTENSIONS = ["jpeg", "png", "bmp", "jpg"]


def password_hash(pswd, salt):
    '''Applies SHA256 hashing to concatenation of provided password and salt'''
    concat = str(pswd) + str(salt)
    return hashlib.sha256(concat.encode()).hexdigest()


def gen_salt():
    '''Generate hexadecimal representation of salt'''
    hex_digits = '0123456789abcdef'
    random_digits = [random.choice(hex_digits) for n in range(16)]
    return ''.join(random_digits)


def valid_password(pswd):
    '''Check if the password is valid. Valid password is the one
    that contains 6 - 100 symbols. Allowed symbols are
    alphanumeric and _*&^%$#@!-+= characters
    Returns True is password satisfies the requirements and False
    otherwise
    '''
    if len(pswd) > 100 or len(pswd) < 6:
        return False
    p = re.compile("[a-zA-Z0-9_*&^%$#@!-+=]+")
    m = p.match(pswd)
    if m:
        #make sure that entire string matches the pattern
        if (m.group() == pswd):
            return True
        else:
            return False


def valid_login_name(lgn):
    '''Check if the login name is valid. Valid login is the one
    that 6 - 100 symbols, and contains only alphanumeric characters.
    Returns True is login name satisfies the requirements and False
    otherwise
    '''
    if len(lgn) > 100 or len(lgn) < 6:
        return False
    p = re.compile("[a-zA-Z0-9]+")
    m = p.match(lgn)
    if m:
        #make sure that entire string matches the pattern
        #print(m.group(), file=sys.stderr)
        if (m.group() == lgn):
            return True
        else:
            return False


def valid_file_ext(f):
    '''Check if file's extension is one of the allowed ones.
    Returns True if extension is valid and False otherwise'''
    name, ext = f.rsplit(".", 1)
    ext = ext.lower()
    return ext in ALLOWED_EXTENSIONS


def upload_file_s3(filepath, bucket, key):
    s3 = boto3.client('s3')
    s3.upload_file(filepath, bucket, key)

def set_file_public_read_s3(bucket, key):
    s3 = boto3.resource('s3')
    s3.ObjectAcl(bucket, key).put(ACL='public-read')

