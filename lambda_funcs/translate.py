import json
import boto3

dynamodb = boto3.resource('dynamodb')
s3 = boto3.resource('s3')
translate = boto3.client('translate')
transcribe_output_bucket = 'krasniko-a3-transcribe'
translate_bucket = 'krasniko-a3-translate'
temp_file_path = '/tmp/hello.txt'

def extract_timing_info(items):
    '''Input must be the dictionary structure stored in items'''
    timings = ''
    text = ''
    sentences = []
    sentence_start = True
    sentence_start_time = ''
    sentence_end_time = ''
    for item in items:
        if 'start_time' in item:
            start = item["start_time"]
            end = item["end_time"]
            word = item["alternatives"][0]["content"]
            if sentence_start:
                sentence_start_time = start
                sentence_start = False
            text += " " + word
        else:
            punctuation = item["alternatives"][0]["content"]
            #print(type(punctuation))
            if punctuation == '.' or punctuation == '?' or punctuation == '!':
                sentence_end_time = end
                timings += "{}-{},".format(sentence_start_time, sentence_end_time)
                sentence_start = True
                sentences.append(text + punctuation)
                text = ""
            else:
                text += punctuation
            
    return sentences, timings
        

def upload_text_to_bucket(text, bucket, key):
    with open(temp_file_path, 'w') as f:
        f.write(text)

    #upload the text file to proper bucket
    s3.meta.client.upload_file(temp_file_path, bucket, key)

def lambda_handler(event, context):
    # extract bucket name and key
    s3_obj = event['Records'][0]['s3']
    bucket_name = s3_obj['bucket']['name']
    object_name = s3_obj['object']['key']
    file_uri = 's3://{}/{}'.format(bucket_name, object_name)
    print(file_uri)
    
    #extract the user name and file name from the object name
    user, filename = object_name.split("-", 1)
    filename_noext = filename.rsplit(".")[0]
    print(user, filename_noext)
    
    # access the database to get the source language and destination languages
    table = dynamodb.Table("files")
    resp = table.get_item(
        Key={"user": user, 'filename': filename_noext+".mp3"}
    )
    print (resp)
    
    #extract source and destination languages
    src_lang = resp["Item"]['srclang']
    dst_lang = resp["Item"]['dstlang']
    
    #this should be the uri for json file from transcribe
    #read it and extract the text
    
    s3 = boto3.resource('s3')
    s3.meta.client.download_file(bucket_name, object_name, temp_file_path)
    
    with open(temp_file_path, 'r') as f:
        json_resp = json.load(f)
        text = json_resp['results']['transcripts'][0]['transcript']
        items = json_resp['results']['items']
        print("ITEMS", items)
        #also need to extract the timings
        sentences, timings = extract_timing_info(items)
        print(timings)
        print( sentences)
    

    #text_bucket = "krasniko-ece1779-a3-text"
    src_text_object = "{}/{}.{}".format(user, filename_noext, src_lang) #'test_en.txt'
    timings_object = "{}/{}.time".format(user, filename_noext)
    #upload the text file to proper bucket
    #s3.meta.client.upload_file(temp_file_path, translate_bucket, src_text_object)
    marked_text = " [1] ".join(sentences)
    upload_text_to_bucket(marked_text, translate_bucket, src_text_object)
    upload_text_to_bucket(timings, translate_bucket, timings_object)
    
    
    print(marked_text)
    response = translate.translate_text(
        Text=marked_text,
        SourceLanguageCode=src_lang, #see here https://docs.aws.amazon.com/translate/latest/dg/what-is.html#what-is-languages
        TargetLanguageCode=dst_lang,
        #ClientToken='string'
    )
    
    
    print(response["TranslatedText"])
    
    # get the translated text, save to temp file and then upload to s3
    dst_text = response["TranslatedText"]
    #with open(temp_file_path, 'w') as f:
    #    f.write(dst_text)
    
    dst_text_object = "{}/{}.{}".format(user, filename_noext, dst_lang)
    #s3.meta.client.upload_file(temp_file_path, translate_bucket, dst_text_object)
    upload_text_to_bucket(dst_text, translate_bucket, dst_text_object)
    
    # update add available attribute, for web app to know processing is done
    table = dynamodb.Table("files")
    resp = table.update_item(
        Key={"user": user, 'filename': filename_noext+".mp3"},
        UpdateExpression = "SET available = :b",
        ExpressionAttributeValues = {":b": True}
    )
    print(resp)
    
    #TODO: maybe also delete the transcription job
    
    #print(event)
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }

