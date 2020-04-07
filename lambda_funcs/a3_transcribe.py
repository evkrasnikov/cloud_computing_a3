import json
import boto3

transcribe_output_bucket = 'krasniko-a3-transcribe'

lang_code_mapping = {"en":'en-US',
    "es":'es-ES',
    "it":'it-IT',
    "fr":'fr-CA'
}

def lambda_handler(event, context):
    print(event)
    if event['Records'][0]["eventName"] != "INSERT":
        return {
        'statusCode': 200,
        'body': json.dumps('Dont care about event {} !'.format(event['Records'][0]["eventName"]))
        }

    # we should be guaranteed to get only 1 record
    record = event['Records'][0]
    new_image = record['dynamodb']['NewImage']
    
    # extract information necessary for transcribing
    user = new_image['user']['S']
    filename = new_image['filename']['S']
    language = new_image['srclang']['S']
    
    # extract bucket name and key
    object_name = "{}/{}".format(user, filename)
    bucket_name = "krasniko-a3-mp3"
    file_uri = 's3://{}/{}'.format(bucket_name, object_name)
    print(file_uri)
    print(language)
    language_code = lang_code_mapping[language]
    print(language_code)
    client = boto3.client('transcribe')
    job_name ="{}_{}".format(user, filename.split(".")[0])
    print(job_name)
    
    response = client.start_transcription_job(
        TranscriptionJobName=job_name,
        LanguageCode=language_code,
        Media={'MediaFileUri': file_uri},
        OutputBucketName=transcribe_output_bucket,
        #JobExecutionSettings={'DataAccessRoleArn':'arn:aws:iam::158238500440:role/s3read_transcribe'}
        )
    
    print(response)
    print(event)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Received file {}, transcribing!'.format(object_name))
    }
