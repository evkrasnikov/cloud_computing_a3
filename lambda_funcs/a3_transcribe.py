import json
import boto3

transcribe_output_bucket = 'krasniko-a3-transcribe'
mp3_bucket_name = "krasniko-a3-mp3"

lang_code_mapping = {"en":'en-US',
    "es":'es-ES',
    "it":'it-IT',
    "fr":'fr-CA'
}

def lambda_handler(event, context):
    '''This function needs to handle only insert events in dynamodb,
    which happen when new file gets added'''
    
    print(event)
    for record in event['Records']:
        if record["eventName"] != "INSERT":
            continue
    
        new_image = record['dynamodb']['NewImage']
        
        # extract information necessary for transcribing
        user = new_image['user']['S']
        filename = new_image['filename']['S']
        language = new_image['srclang']['S']
        
        # extract bucket name and key
        object_name = "{}/{}".format(user, filename)
        file_uri = 's3://{}/{}'.format(mp3_bucket_name, object_name)
        print(file_uri)
        print(language)
        language_code = lang_code_mapping[language]
        print(language_code)
        client = boto3.client('transcribe')
        job_name ="{}-{}".format(user, filename.split(".")[0])
        print(job_name)
        
        response = client.start_transcription_job(
            TranscriptionJobName=job_name,
            LanguageCode=language_code,
            Media={'MediaFileUri': file_uri},
            OutputBucketName=transcribe_output_bucket,
            )
        
        print(response)
        print(event)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Done processing DB events')
    }
